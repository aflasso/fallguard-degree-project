"""
Debug visual: inspecciona frame a frame cómo YOLO y MediaPipe detectan la persona.

Controles:
  ESPACIO  → siguiente frame
  A        → frame anterior
  Q        → salir

Uso:
  python debug_visual.py \
      --video       "Coffee_room/Videos/video (1).avi" \
      --model_path  "./yolo11_tunned.pt" \
      --pose_model_path "./pose_landmarker.task" \
      [--conf 0.3] \
      [--device cpu]
"""

import cv2
import argparse
import numpy as np
from pathlib import Path

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from ultralytics import YOLO


# ──────────────────────────────────────────────────────────────────────────────
# MediaPipe connections (para dibujar el esqueleto)
# ──────────────────────────────────────────────────────────────────────────────
POSE_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,7),(0,4),(4,5),(5,6),(6,8),
    (9,10),(11,12),(11,13),(13,15),(15,17),(15,19),(15,21),(17,19),
    (12,14),(14,16),(16,18),(16,20),(16,22),(18,20),
    (11,23),(12,24),(23,24),(23,25),(24,26),(25,27),(26,28),
    (27,29),(28,30),(29,31),(30,32),(27,31),(28,32),
]


def build_pose_detector(pose_model_path: str):
    base_options = python.BaseOptions(model_asset_path=pose_model_path)
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.IMAGE,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
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


def draw_skeleton_on_frame(frame, landmarks, x1, y1, x2, y2):
    """Dibuja los landmarks de MediaPipe sobre el frame completo (no el crop)."""
    crop_w = x2 - x1
    crop_h = y2 - y1

    points = {}
    for i, lm in enumerate(landmarks):
        px = int(x1 + lm.x * crop_w)
        py = int(y1 + lm.y * crop_h)
        points[i] = (px, py)
        vis = lm.visibility
        color = (0, int(255 * vis), int(255 * (1 - vis)))
        cv2.circle(frame, (px, py), 4, color, -1)

    for a, b in POSE_CONNECTIONS:
        if a in points and b in points:
            cv2.line(frame, points[a], points[b], (0, 255, 180), 2)

    return frame


def draw_overlay(frame, frame_idx, total, bbox, kp_detected, conf_val):
    """Dibuja HUD con info del frame."""
    h, w = frame.shape[:2]

    # Fondo semitransparente arriba
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 60), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

    # Texto info
    yolo_status = f"YOLO: OK  conf={conf_val:.2f}" if bbox else "YOLO: NO DETECTION"
    mp_status   = "MediaPipe: OK" if kp_detected else "MediaPipe: NO POSE"
    yolo_color  = (0, 255, 100) if bbox else (0, 80, 255)
    mp_color    = (0, 255, 100) if kp_detected else (0, 80, 255)

    cv2.putText(frame, f"Frame {frame_idx}/{total}", (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    cv2.putText(frame, yolo_status, (10, 42),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, yolo_color, 1)
    cv2.putText(frame, mp_status, (w // 2, 42),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, mp_color, 1)

    # Instrucciones abajo
    cv2.rectangle(frame, (0, h - 28), (w, h), (0, 0, 0), -1)
    cv2.putText(frame, "ESPACIO: siguiente  |  A: anterior  |  Q: salir",
                (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

    return frame


def process_frame(frame_bgr, model, detector, conf, device):
    """
    Corre YOLO + MediaPipe sobre un frame y retorna:
      - frame anotado
      - bbox encontrada (o None)
      - keypoints detectados (bool)
      - confianza YOLO
    """
    display = frame_bgr.copy()
    bbox = None
    kp_detected = False
    conf_val = 0.0

    # YOLO — detección simple (sin tracking para el debugger)
    results = model(frame_bgr, conf=conf, device=device, classes=[0], verbose=False)
    boxes = results[0].boxes

    if boxes is not None and len(boxes) > 0:
        # Tomar la detección con mayor confianza
        best_idx = int(boxes.conf.argmax())
        conf_val = float(boxes.conf[best_idx])
        x1, y1, x2, y2 = boxes.xyxy[best_idx].int().tolist()
        cx1, cy1, cx2, cy2 = safe_crop(frame_bgr, x1, y1, x2, y2)
        bbox = (cx1, cy1, cx2, cy2)

        # Dibujar bbox YOLO
        cv2.rectangle(display, (x1, y1), (x2, y2), (255, 180, 0), 2)
        cv2.rectangle(display, (cx1, cy1), (cx2, cy2), (255, 255, 0), 1)  # crop con margen
        cv2.putText(display, f"{conf_val:.2f}", (x1, y1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 180, 0), 1)

        # MediaPipe sobre el crop
        crop = frame_bgr[cy1:cy2, cx1:cx2]
        if crop.size > 0:
            crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=crop_rgb)
            result = detector.detect(mp_image)

            if result.pose_landmarks:
                kp_detected = True
                draw_skeleton_on_frame(display, result.pose_landmarks[0],
                                       cx1, cy1, cx2, cy2)

    draw_overlay(display, 0, 0, bbox, kp_detected, conf_val)
    return display, bbox, kp_detected, conf_val


def main():
    parser = argparse.ArgumentParser(description="Debug visual YOLO + MediaPipe frame a frame.")
    parser.add_argument("--video",           type=str, required=True,  help="Ruta al video .avi")
    parser.add_argument("--model_path",      type=str, required=True,  help="Ruta al modelo YOLO (.pt)")
    parser.add_argument("--pose_model_path", type=str, default="pose_landmarker.task",
                        help="Ruta al modelo MediaPipe (.task)")
    parser.add_argument("--conf",   type=float, default=0.7,   help="Confianza YOLO (default: 0.3)")
    parser.add_argument("--device", type=str,   default="cpu", help="'cpu' o 'cuda:0'")
    args = parser.parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        raise FileNotFoundError(f"Video no encontrado: {video_path}")

    pose_path = Path(args.pose_model_path)
    if not pose_path.exists():
        raise FileNotFoundError(
            f"Modelo MediaPipe no encontrado: {pose_path}\n"
            "Descárgalo con:\n"
            "  wget -O pose_landmarker.task https://storage.googleapis.com/mediapipe-models/"
            "pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"
        )

    print("🔧 Cargando modelos...")
    model    = YOLO(args.model_path)
    detector = build_pose_detector(str(pose_path))
    print("✅ Modelos cargados")

    # Cargar todos los frames en memoria (dataset pequeño 320x240)
    cap = cv2.VideoCapture(str(video_path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"📹 Video: {video_path.name} — {total} frames")
    print("   Cargando frames... (puede tardar un momento)")

    raw_frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        raw_frames.append(frame)
    cap.release()

    total = len(raw_frames)
    cache = {}  # frame_idx → display procesado

    def get_display(idx):
        if idx not in cache:
            frame = raw_frames[idx]
            display, bbox, kp_detected, conf_val = process_frame(
                frame, model, detector, args.conf, args.device
            )
            # Re-dibujar overlay con número de frame correcto
            h, w = display.shape[:2]
            # Borrar el frame 0/0 y reescribir
            cv2.putText(display, f"Frame {idx+1}/{total}", (10, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(display, f"Frame {idx+1}/{total}", (10, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            cache[idx] = display
        return cache[idx]

    print("\n🎬 Abriendo visor...")
    print("   ESPACIO → siguiente frame")
    print("   A       → frame anterior")
    print("   Q       → salir\n")

    cv2.namedWindow("Debug YOLO + MediaPipe", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Debug YOLO + MediaPipe", 800, 600)

    idx = 0
    while True:
        display = get_display(idx)
        cv2.imshow("Debug YOLO + MediaPipe", display)

        key = cv2.waitKey(0) & 0xFF

        if key == ord('q') or key == 27:  # Q o ESC
            break
        elif key == ord(' '):             # ESPACIO → siguiente
            idx = min(idx + 1, total - 1)
        elif key == ord('a'):             # A → anterior
            idx = max(idx - 1, 0)

    cv2.destroyAllWindows()
    detector.close()
    print("✔  Visor cerrado.")


if __name__ == "__main__":
    main()