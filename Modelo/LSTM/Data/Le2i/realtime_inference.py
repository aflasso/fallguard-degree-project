"""
Inferencia en tiempo real para detección de caídas.

Pipeline por frame:
  1. Captura frame de cámara
  2. YOLO detecta persona → bbox
  3. MediaPipe extrae keypoints del crop
  4. Se mantiene ventana deslizante de N frames
  5. LSTM predice clase cada frame
  6. Se muestra resultado en pantalla

Controles:
  Q → salir

Uso:
  python realtime_inference.py \
      --model_path       "lstm_data/fall_lstm_final.pt" \
      --yolo_path        "./yolo11x.pt" \
      --pose_model_path  "./pose_landmarker.task" \
      [--camera          0] \
      [--conf            0.3] \
      [--device          cpu]
"""

import cv2
import argparse
import numpy as np
import torch
import torch.nn as nn
from collections import deque
from pathlib import Path

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
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
COCO_INDICES = [0, 1, 2, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]

POSE_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,7),(0,4),(4,5),(5,6),(6,8),
    (9,10),(11,12),(11,13),(13,15),(15,17),(15,19),(15,21),
    (12,14),(14,16),(16,18),(16,20),(16,22),
    (11,23),(12,24),(23,24),(23,25),(24,26),(25,27),(26,28),
    (27,29),(28,30),(27,31),(28,32),
]

LABEL_COLORS = {
    0: (0, 200, 0),    # Normal → verde
    1: (0, 0, 255),    # Caída → rojo
    2: (0, 165, 255),  # Post-caída → naranja
}
LABEL_NAMES_DISPLAY = {
    0: "NORMAL",
    1: "CAIDA DETECTADA",
    2: "PERSONA EN EL PISO",
}


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def build_pose_detector(pose_model_path: str):
    base_options = python.BaseOptions(model_asset_path=pose_model_path)
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.IMAGE,
        num_poses=1,
        min_pose_detection_confidence=0.3,
        min_pose_presence_confidence=0.3,
        min_tracking_confidence=0.3,
        output_segmentation_masks=False,
    )
    return vision.PoseLandmarker.create_from_options(options)


def safe_crop(frame, x1, y1, x2, y2, margin=0.05):
    h, w = frame.shape[:2]
    pad_x = int((x2 - x1) * margin)
    pad_y = int((y2 - y1) * margin)
    return (
        max(0, x1 - pad_x), max(0, y1 - pad_y),
        min(w, x2 + pad_x), min(h, y2 + pad_y),
    )


def extract_features(crop_bgr, detector, cx1, cy1, cx2, cy2, frame_bgr):
    """Extrae features del crop: x,y de 17 puntos COCO."""
    if crop_bgr is None or crop_bgr.size == 0:
        return None, None

    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=crop_rgb)
    result   = detector.detect(mp_image)

    if not result.pose_landmarks:
        return None, None

    landmarks = result.pose_landmarks[0]
    kps = np.zeros(len(COCO_INDICES) * 2, dtype=np.float32)
    for i, idx in enumerate(COCO_INDICES):
        kps[i*2]   = landmarks[idx].x
        kps[i*2+1] = landmarks[idx].y

    # Dibujar esqueleto en frame
    crop_w = cx2 - cx1
    crop_h = cy2 - cy1
    points = {}
    for idx in range(len(landmarks)):
        px = int(cx1 + landmarks[idx].x * crop_w)
        py = int(cy1 + landmarks[idx].y * crop_h)
        points[idx] = (px, py)
        cv2.circle(frame_bgr, (px, py), 3, (0, 255, 180), -1)

    for a, b in POSE_CONNECTIONS:
        if a in points and b in points:
            cv2.line(frame_bgr, points[a], points[b], (0, 255, 180), 1)

    return kps, points


def compute_velocity(buffer):
    """Calcula velocidad entre frames consecutivos en el buffer."""
    arr = np.array(buffer)          # (T, 34)
    vel = np.zeros_like(arr)
    vel[1:] = arr[1:] - arr[:-1]   # diferencia entre frames
    return np.concatenate([arr, vel], axis=1)  # (T, 68)


def draw_hud(frame, label, probs, label_names, label_colors, fps, window_fill):
    h, w = frame.shape[:2]
    color = label_colors.get(label, (200, 200, 200))
    name  = label_names.get(label, "?")

    # Fondo superior
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 75), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    # Etiqueta principal
    cv2.putText(frame, name, (10, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)

    # Probabilidades
    prob_txt = f"P: N={probs[0]:.2f}  C={probs[1]:.2f}  P={probs[2]:.2f}"
    cv2.putText(frame, prob_txt, (10, 62),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    # FPS y buffer
    cv2.putText(frame, f"FPS: {fps:.1f}  Buffer: {window_fill}",
                (w - 200, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    # Barra de alerta si es caída
    if label == 1:
        cv2.rectangle(frame, (0, h-8), (w, h), (0, 0, 255), -1)

    return frame


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Inferencia en tiempo real — detección de caídas.")
    parser.add_argument("--model_path",      type=str, required=True)
    parser.add_argument("--yolo_path",        type=str, required=True)
    parser.add_argument("--pose_model_path",  type=str, default="pose_landmarker.task")
    parser.add_argument("--source", type=str, default="0",
                        help="Fuente de video: '0' para cámara, ruta a video .avi/.mp4")
    parser.add_argument("--conf",             type=float, default=0.3)
    parser.add_argument("--device",           type=str, default="cuda:0")
    args = parser.parse_args()

    # ── Cargar checkpoint ──────────────────────────────────────────────────
    checkpoint = torch.load(args.model_path, map_location="cpu")
    hp         = checkpoint["hyperparams"]
    label_map  = checkpoint["label_map"]       # {-1:0, 0:1, 1:2}
    inv_map    = {v: k for k, v in label_map.items()}  # {0:-1, 1:0, 2:1}

    WINDOW     = hp["window"]
    N_FEATURES = hp["input_size"]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model  = FallLSTM(
        input_size=hp["input_size"],
        hidden_size=hp["hidden_size"],
        num_layers=hp["num_layers"],
        num_classes=hp["num_classes"],
        dropout=hp["dropout"],
    ).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    print(f"✅ Modelo cargado | ventana={WINDOW} | features={N_FEATURES}")

    # ── Cargar YOLO y MediaPipe ────────────────────────────────────────────
    yolo     = YOLO(args.yolo_path)
    detector = build_pose_detector(args.pose_model_path)
    print("✅ YOLO y MediaPipe cargados")

    # ── Fuente de video ───────────────────────────────────────────────────
    # Intentar convertir a int (cámara) o usar como ruta (video)
    try:
        source = int(args.source)
        source_name = f"cámara {source}"
    except ValueError:
        source = args.source
        source_name = args.source

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"No se pudo abrir: {source_name}")
    print(f"📹 Fuente: {source_name}")

    cv2.namedWindow("Fall Detection", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Fall Detection", 960, 720)

    kp_buffer      = deque(maxlen=WINDOW)  # buffer de keypoints x,y
    label          = 0                      # Normal por defecto
    probs          = [1.0, 0.0, 0.0]
    fps            = 0.0
    prev_time      = cv2.getTickCount()
    missing_frames = 0
    MAX_MISSING    = 10  # frames sin detección antes de resetear

    print("\n🎬 Iniciando inferencia en tiempo real... (Q para salir)\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # FPS
        curr_time = cv2.getTickCount()
        fps = cv2.getTickFrequency() / (curr_time - prev_time)
        prev_time = curr_time

        # YOLO
        results = yolo(frame, conf=args.conf, device=args.device,
                       classes=[0], verbose=False)
        boxes = results[0].boxes

        kps_frame = None
        if boxes is not None and len(boxes) > 0:
            best_idx = int(boxes.conf.argmax())
            x1, y1, x2, y2 = boxes.xyxy[best_idx].int().tolist()
            cx1, cy1, cx2, cy2 = safe_crop(frame, x1, y1, x2, y2)

            # Dibujar bbox
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 180, 0), 2)

            crop = frame[cy1:cy2, cx1:cx2]
            kps_frame, _ = extract_features(crop, detector, cx1, cy1, cx2, cy2, frame)

        # Actualizar buffer y predecir
        if kps_frame is not None:
            missing_frames = 0
            kp_buffer.append(kps_frame)
            # Inferencia solo cuando el buffer está lleno
            if len(kp_buffer) == WINDOW:
                features = compute_velocity(list(kp_buffer))
                X = torch.tensor(features, dtype=torch.float32).unsqueeze(0).to(device)
                with torch.no_grad():
                    logits = model(X)
                    probs_tensor = torch.softmax(logits, dim=1)[0].cpu().numpy()
                probs = probs_tensor.tolist()
                label = int(np.argmax(probs))

                # Log en consola cuando detecta caída
                if label == 1:
                    import datetime
                    ts = datetime.datetime.now().strftime("%H:%M:%S")
                    print(f"⚠️  [{ts}] CAÍDA DETECTADA — confianza: {probs[1]:.2%}")
        else:
            # Mantener secuencia temporal de MediaPipe aunque no haya bbox
            dummy = np.zeros((10, 10, 3), dtype=np.uint8)
            dummy_mp = mp.Image(image_format=mp.ImageFormat.SRGB, data=dummy)
            try:
                detector.detect_for_video(dummy_mp)
            except Exception:
                pass
            missing_frames += 1
            if missing_frames > MAX_MISSING:
                # Persona ausente demasiado tiempo → resetear
                kp_buffer.clear()
                label = 0
                probs = [1.0, 0.0, 0.0]
                missing_frames = 0
            # Si missing <= MAX → mantener última predicción (tolera pérdida durante caída)

        # HUD
        draw_hud(frame, label, probs, LABEL_NAMES_DISPLAY, LABEL_COLORS,
                 fps, len(kp_buffer))

        cv2.imshow("Fall Detection", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    detector.close()
    cv2.destroyAllWindows()
    print("✔  Inferencia terminada.")


if __name__ == "__main__":
    main()