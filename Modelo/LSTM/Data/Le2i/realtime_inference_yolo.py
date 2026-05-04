"""
Inferencia en tiempo real para detección de caídas.

Pipeline por frame:
  1. Captura frame de cámara o video
  2. YOLO-pose detecta persona y extrae keypoints en una sola pasada
  3. Se mantiene ventana deslizante de N frames
  4. LSTM predice clase cada frame
  5. Lógica de evento: se confirma caída solo cuando hay MIN_FRAMES consecutivos
     con pred==1 y conf_media >= CONF_LSTM
  6. Se muestra resultado en pantalla

Controles:
  Q -> salir

Uso:
  python realtime_inference_yolo.py `
      --model_path  "lstm_data/fall_lstm_final.pt" `
      --yolo_path   "./yolo11x-pose.pt" `
      --source     0 `
      --conf       0.8 `
      --conf_lstm  0.7 `
      --min_frames 3 `
      --device     cuda:0
"""

import cv2
import argparse
import datetime
import numpy as np
import torch
import torch.nn as nn
from collections import deque

from ultralytics import YOLO


# ──────────────────────────────────────────────────────────────────────────────
# Modelo LSTM
# ──────────────────────────────────────────────────────────────────────────────
class FallLSTM(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, num_classes, dropout):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_size, num_classes)

    def forward(self, x):
        out, _ = self.lstm(x)
        out = out[:, -1, :]
        out = self.dropout(out)
        return self.fc(out)


# ──────────────────────────────────────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────────────────────────────────────
KEYPOINT_MAP = [
    (0,  "kp_0"),   # nose
    (1,  "kp_1"),   # left eye
    (2,  "kp_2"),   # right eye
    (3,  "kp_7"),   # left ear
    (4,  "kp_8"),   # right ear
    (5,  "kp_11"),  # left shoulder
    (6,  "kp_12"),  # right shoulder
    (7,  "kp_13"),  # left elbow
    (8,  "kp_14"),  # right elbow
    (9,  "kp_15"),  # left wrist
    (10, "kp_16"),  # right wrist
    (11, "kp_23"),  # left hip
    (12, "kp_24"),  # right hip
    (13, "kp_25"),  # left knee
    (14, "kp_26"),  # right knee
    (15, "kp_27"),  # left ankle
    (16, "kp_28"),  # right ankle
]
COCO_INDICES = [coco_idx for coco_idx, _ in KEYPOINT_MAP]

SKELETON_CONNECTIONS = [
    (0, 1), (0, 2),
    (1, 3), (2, 4),
    (5, 6),
    (5, 7), (7, 9),
    (6, 8), (8, 10),
    (5, 11), (6, 12),
    (11, 12),
    (11, 13), (13, 15),
    (12, 14), (14, 16),
]

LABEL_COLORS = {
    0: (0, 200, 0),
    1: (0, 0, 255),
    2: (0, 165, 255),
}
LABEL_NAMES_DISPLAY = {
    0: "NORMAL",
    1: "CAIDA DETECTADA",
    2: "PERSONA EN EL PISO",
}


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def extract_features(results, frame_bgr):
    boxes    = results[0].boxes
    kps_data = results[0].keypoints

    if boxes is None or len(boxes) == 0:
        return None, None
    if kps_data is None or len(kps_data.xyn) == 0:
        return None, None

    best_idx = int(boxes.conf.argmax())
    xyn = kps_data.xyn[best_idx].cpu().numpy()
    xy  = kps_data.xy[best_idx].cpu().numpy()

    kps    = np.zeros(len(COCO_INDICES) * 2, dtype=np.float32)
    points = {}

    for map_idx, coco_idx in enumerate(COCO_INDICES):
        kps[map_idx * 2]     = xyn[coco_idx, 0]
        kps[map_idx * 2 + 1] = xyn[coco_idx, 1]
        px, py = int(xy[coco_idx, 0]), int(xy[coco_idx, 1])
        points[map_idx] = (px, py)
        cv2.circle(frame_bgr, (px, py), 3, (0, 255, 180), -1)

    for a, b in SKELETON_CONNECTIONS:
        if a in points and b in points:
            cv2.line(frame_bgr, points[a], points[b], (0, 255, 180), 1)

    return kps, points


def build_features(buffer):
    arr = np.array(buffer, dtype=np.float32)
    vel = np.zeros_like(arr)
    vel[1:] = arr[1:] - arr[:-1]
    return np.concatenate([arr, vel], axis=1)


def draw_hud(frame, display_label, probs, alert_active, fps, window_fill, conf_lstm_threshold):
    h, w = frame.shape[:2]
    color = LABEL_COLORS.get(display_label, (200, 200, 200))
    name  = LABEL_NAMES_DISPLAY.get(display_label, "?")

    # Si hay alerta activa forzar color rojo independiente del label display
    if alert_active:
        color = (0, 0, 255)
        name  = "CAIDA CONFIRMADA"

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 90), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    cv2.putText(frame, name, (10, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)

    prob_txt = f"P: N={probs[0]:.2f}  C={probs[1]:.2f}  P={probs[2]:.2f}"
    cv2.putText(frame, prob_txt, (10, 62),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    cv2.putText(frame, f"FPS:{fps:.1f}  Buffer:{window_fill}  conf_lstm≥{conf_lstm_threshold:.2f}",
                (10, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)

    if alert_active:
        cv2.rectangle(frame, (0, h - 8), (w, h), (0, 0, 255), -1)

    return frame


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Inferencia en tiempo real — detección de caídas.")
    parser.add_argument("--model_path", type=str, required=True)
    parser.add_argument("--yolo_path",  type=str, required=True)
    parser.add_argument("--source",     type=str, default="0",
                        help="Fuente: '0' camara, ruta a video .avi/.mp4")
    parser.add_argument("--conf",       type=float, default=0.8,
                        help="Confianza minima YOLO. Default: 0.8")
    parser.add_argument("--conf_lstm",  type=float, default=0.7,
                        help="Confianza media minima del LSTM para confirmar caida. Default: 0.7")
    parser.add_argument("--min_frames", type=int,   default=3,
                        help="Frames consecutivos con pred==1 para confirmar caida. Default: 3")
    parser.add_argument("--device",     type=str,   default="cuda:0")
    args = parser.parse_args()

    # ── Cargar LSTM ───────────────────────────────────────────────────────
    checkpoint = torch.load(args.model_path, map_location="cpu")
    hp         = checkpoint["hyperparams"]
    WINDOW     = hp["window"]

    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    model  = FallLSTM(
        input_size=hp["input_size"],
        hidden_size=hp["hidden_size"],
        num_layers=hp["num_layers"],
        num_classes=hp["num_classes"],
        dropout=hp["dropout"],
    ).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    print(f"✅ LSTM cargado | ventana={WINDOW} | features={hp['input_size']}")

    # ── Cargar YOLO-pose ──────────────────────────────────────────────────
    yolo = YOLO(args.yolo_path)
    print(f"✅ YOLO-pose cargado")
    print(f"   conf_yolo={args.conf}  conf_lstm={args.conf_lstm}  min_frames={args.min_frames}\n")

    # ── Fuente de video ───────────────────────────────────────────────────
    try:
        source = int(args.source)
        source_name = f"camara {source}"
    except ValueError:
        source = args.source
        source_name = args.source

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"No se pudo abrir: {source_name}")
    print(f"📹 Fuente: {source_name}")

    cv2.namedWindow("Fall Detection", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Fall Detection", 960, 720)

    # ── Estado del sistema ────────────────────────────────────────────────
    kp_buffer      = deque(maxlen=WINDOW)
    probs          = [1.0, 0.0, 0.0]
    display_label  = 0
    fps            = 0.0
    prev_time      = cv2.getTickCount()
    missing_frames = 0
    MAX_MISSING    = 10

    # Estado del evento de caída en curso
    fall_streak_confs = deque(maxlen=args.min_frames)  # ventana deslizante de confianzas
    alert_active      = False   # True cuando el evento fue confirmado
    alert_silence     = 0       # frames sin pred==1 tras alerta
    ALERT_COOLDOWN    = 30      # frames sin caída para desactivar alerta

    print("🎬 Iniciando inferencia... (Q para salir)\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        curr_time = cv2.getTickCount()
        fps = cv2.getTickFrequency() / (curr_time - prev_time)
        prev_time = curr_time

        results = yolo(frame, conf=args.conf, device=args.device, verbose=False)

        boxes = results[0].boxes
        if boxes is not None and len(boxes) > 0:
            best_idx = int(boxes.conf.argmax())
            x1, y1, x2, y2 = boxes.xyxy[best_idx].int().tolist()
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 180, 0), 2)

        kps_frame, _ = extract_features(results, frame)

        if kps_frame is not None:
            missing_frames = 0
            kp_buffer.append(kps_frame)

            if len(kp_buffer) == WINDOW:
                features = build_features(list(kp_buffer))
                X = torch.tensor(features, dtype=torch.float32).unsqueeze(0).to(device)
                with torch.no_grad():
                    logits       = model(X)
                    probs_tensor = torch.softmax(logits, dim=1)[0].cpu().numpy()
                probs         = probs_tensor.tolist()
                display_label = int(np.argmax(probs))
                prob_caida    = float(probs[1])

                # ── Lógica de evento ──────────────────────────────────────
                if display_label == 1:
                    fall_streak_confs.append(prob_caida)
                    alert_silence = 0

                    # Verificar ventana deslizante de los ultimos min_frames
                    if (not alert_active
                            and len(fall_streak_confs) == args.min_frames
                            and np.mean(fall_streak_confs) >= args.conf_lstm):
                            alert_active = True
                            ts = datetime.datetime.now().strftime("%H:%M:%S")
                            print(f"⚠️  [{ts}] CAIDA CONFIRMADA — "
                                  f"conf_media_ultimos_{args.min_frames}={np.mean(fall_streak_confs):.2%}")
                else:
                    # Resetear acumulador si ya no hay caida
                    if not alert_active:
                        fall_streak_confs.clear()
                    else:
                        # Alerta activa: contar silencio para desactivarla
                        alert_silence += 1
                        if alert_silence >= ALERT_COOLDOWN:
                            alert_active      = False
                            fall_streak_confs.clear()
                            alert_silence     = 0

        else:
            missing_frames += 1
            if missing_frames > MAX_MISSING:
                kp_buffer.clear()
                display_label     = 0
                probs             = [1.0, 0.0, 0.0]
                alert_active      = False
                fall_streak_confs = []
                alert_silence     = 0
                missing_frames    = 0

        draw_hud(frame, display_label, probs, alert_active,
                 fps, len(kp_buffer), args.conf_lstm)

        cv2.imshow("Fall Detection", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("✔  Inferencia terminada.")


if __name__ == "__main__":
    main()