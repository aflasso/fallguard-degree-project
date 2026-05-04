"""
Pipeline: Extracción de keypoints por frame para detección de caídas.

Flujo por video:
  1. Carga el CSV de anotaciones (annotations_csv/video (i).csv)
  2. Abre el video correspondiente (Videos/video (i).avi)
  3. Por cada frame:
       - YOLO detecta personas, se toma la bbox con mayor confianza
       - El recorte (crop) se pasa a MediaPipe Pose Landmarker (modo VIDEO)
       - Se extraen 33 landmarks × (x, y, z, visibility) = 132 valores
       - Si YOLO o MediaPipe fallan → fila con keypoints NaN
  4. Guarda un CSV: keypoints_csv/video (i).csv

Columnas de salida:
  frame, label,
  kp_0_x, kp_0_y, kp_0_z, kp_0_vis, ... kp_32_vis

REQUISITO — modelo MediaPipe:
  wget -O pose_landmarker.task https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task

Uso:
  python extract_keypoints.py \
      --dataset_dir      "nombre_carpeta" \
      --model_path       "ruta/a/yolo.pt" \
      --pose_model_path  "pose_landmarker.task" \
      [--conf        0.3] \
      [--iou         0.45] \
      [--img_size    320] \
      [--device      cpu]
"""

import cv2
import csv
import argparse
import numpy as np
import pandas as pd
from pathlib import Path

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from ultralytics import YOLO


# ──────────────────────────────────────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────────────────────────────────────
N_LANDMARKS = 33
KP_COLS = [f"kp_{i}_{dim}" for i in range(N_LANDMARKS) for dim in ("x", "y", "z", "vis")]
EMPTY_KPS = [np.nan] * (N_LANDMARKS * 4)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_video_files(videos_dir: Path):
    return {p.stem: p for p in sorted(videos_dir.glob("*.avi"))}


def get_annotation_files(annotations_dir: Path):
    return {p.stem: p for p in sorted(annotations_dir.glob("*.csv"))}


def load_label_map(csv_path: Path) -> dict:
    df = pd.read_csv(csv_path)
    return dict(zip(df["frame"].astype(int), df["label"].astype(int)))


def build_pose_detector(pose_model_path: str):
    """
    Crea el PoseLandmarker en modo VIDEO para aprovechar el tracking
    temporal entre frames consecutivos.
    Defaults de MediaPipe: 0.5 para los tres umbrales.
    """
    base_options = python.BaseOptions(model_asset_path=pose_model_path)
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        output_segmentation_masks=False,
    )
    return vision.PoseLandmarker.create_from_options(options)


def safe_crop(frame, x1, y1, x2, y2, margin: float = 0.05):
    h, w = frame.shape[:2]
    pad_x = int((x2 - x1) * margin)
    pad_y = int((y2 - y1) * margin)
    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)
    x2 = min(w, x2 + pad_x)
    y2 = min(h, y2 + pad_y)
    return frame[y1:y2, x1:x2]


def extract_keypoints_from_crop(crop_bgr, detector, timestamp_ms: int) -> list:
    """
    Pasa el recorte BGR al PoseLandmarker (modo VIDEO) y retorna 132 floats
    o EMPTY_KPS si falla.
    """
    if crop_bgr is None or crop_bgr.size == 0:
        return EMPTY_KPS
    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=crop_rgb)
    result = detector.detect_for_video(mp_image, timestamp_ms)
    if not result.pose_landmarks:
        return EMPTY_KPS
    kps = []
    for lm in result.pose_landmarks[0]:
        kps.extend([lm.x, lm.y, lm.z, lm.visibility])
    return kps


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline — pasada única
# ──────────────────────────────────────────────────────────────────────────────

def process_video(
    video_path: Path,
    label_map: dict,
    model: YOLO,
    detector,
    conf: float,
    iou: float,
    img_size: int,
    device: str,
) -> list:

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"    ⚠  No se pudo abrir: {video_path}")
        return []

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0  # fallback a 25 FPS (dataset LE2I)
    print(f"    → Procesando {total_frames} frames a {fps:.1f} FPS (pasada única)...")

    rows = []
    frame_idx = 0

    while True:
        ret, frame_bgr = cap.read()
        if not ret:
            break

        frame_idx += 1
        label = label_map.get(frame_idx, -1)
        kps = EMPTY_KPS

        # Timestamp en ms para MediaPipe VIDEO mode
        timestamp_ms = int((frame_idx - 1) * (1000.0 / fps))

        # YOLO — detección simple, tomar bbox de mayor confianza
        results = model(
            frame_bgr,
            conf=conf,
            iou=iou,
            imgsz=img_size,
            device=device,
            classes=[0],
            verbose=False,
        )
        boxes = results[0].boxes

        if boxes is not None and len(boxes) > 0:
            best_idx = int(boxes.conf.argmax())
            x1, y1, x2, y2 = boxes.xyxy[best_idx].int().tolist()
            crop = safe_crop(frame_bgr, x1, y1, x2, y2)
            kps = extract_keypoints_from_crop(crop, detector, timestamp_ms)
        else:
            # Sin detección YOLO: igual hay que llamar a MediaPipe para
            # mantener la secuencia temporal correcta (modo VIDEO lo requiere)
            extract_keypoints_from_crop(None, detector, timestamp_ms)

        row = {"frame": frame_idx, "label": label}
        for col, val in zip(KP_COLS, kps):
            row[col] = val
        rows.append(row)

        if frame_idx % 50 == 0:
            print(f"    → {frame_idx}/{total_frames} frames procesados...")

    cap.release()
    return rows


def save_csv(rows: list, output_path: Path):
    if not rows:
        return
    fieldnames = ["frame", "label"] + KP_COLS
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extrae keypoints por frame (YOLO + MediaPipe Tasks) para el dataset LE2I."
    )
    parser.add_argument("--dataset_dir",     type=str, required=True)
    parser.add_argument("--model_path",      type=str, required=True)
    parser.add_argument("--pose_model_path", type=str, default="pose_landmarker.task")
    parser.add_argument("--conf",     type=float, default=0.7)
    parser.add_argument("--iou",      type=float, default=0.45)
    parser.add_argument("--img_size", type=int,   default=320)
    parser.add_argument("--output_dir", type=str,   default=None,  help="Carpeta de salida para los CSVs. Default: dataset_dir/keypoints_csv")
    parser.add_argument("--device",   type=str,   default="cuda:0")
    args = parser.parse_args()

    dataset_dir     = Path(args.dataset_dir).resolve()
    annotations_dir = dataset_dir / "annotations_csv"
    videos_dir      = dataset_dir / "Videos"
    output_dir      = Path(args.output_dir).resolve() if args.output_dir else dataset_dir / "keypoints_csv"
    output_dir.mkdir(exist_ok=True)

    for d, name in [(annotations_dir, "annotations_csv"), (videos_dir, "Videos")]:
        if not d.exists():
            raise FileNotFoundError(f"No se encontró '{name}' en: {dataset_dir}")

    pose_model_path = Path(args.pose_model_path)
    if not pose_model_path.exists():
        raise FileNotFoundError(
            f"Modelo MediaPipe no encontrado: {pose_model_path}\n"
            "Descárgalo con:\n"
            "  wget -O pose_landmarker.task https://storage.googleapis.com/mediapipe-models/"
            "pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"
        )

    video_files      = get_video_files(videos_dir)
    annotation_files = get_annotation_files(annotations_dir)
    common_stems     = sorted(set(video_files) & set(annotation_files))

    print(f"\n📂 Dataset: {dataset_dir}")
    print(f"📄 Videos con anotación: {len(common_stems)}\n")

    print("🔧 Cargando modelos...")
    model = YOLO(args.model_path)
    print("✅ Modelos cargados\n")

    for stem in common_stems:
        video_path  = video_files[stem]
        annot_path  = annotation_files[stem]
        output_path = output_dir / f"{stem}.csv"

        if output_path.exists():
            print(f"  ⏭  Ya existe, saltando: {stem}.csv")
            continue

        print(f"🎬 [{stem}]")

        # Crear detector nuevo por video (modo VIDEO no puede reutilizarse entre videos)
        detector = build_pose_detector(str(pose_model_path))

        label_map = load_label_map(annot_path)
        rows = process_video(
            video_path=video_path,
            label_map=label_map,
            model=model,
            detector=detector,
            conf=args.conf,
            iou=args.iou,
            img_size=args.img_size,
            device=args.device,
        )
        detector.close()

        save_csv(rows, output_path)

        labels  = [r["label"] for r in rows]
        n_empty = sum(1 for r in rows if np.isnan(r[KP_COLS[0]]))
        print(
            f"    ✅ {output_path.name} | "
            f"frames: {len(rows)}  "
            f"(-1: {labels.count(-1)}, 0: {labels.count(0)}, 1: {labels.count(1)})  "
            f"sin_kps: {n_empty}\n"
        )

    print(f"✔  Pipeline completado. CSVs en:\n   {output_dir}")


if __name__ == "__main__":
    main()