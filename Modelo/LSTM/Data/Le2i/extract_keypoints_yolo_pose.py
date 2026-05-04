"""
Pipeline: Extracción de keypoints por frame para detección de caídas.
Versión: YOLO11x-pose (reemplaza YOLO + MediaPipe por un solo modelo).

Flujo por video:
  1. Carga el CSV de anotaciones (annotations_csv/video (i).csv)
  2. Abre el video correspondiente (Videos/video (i).avi)
  3. Por cada frame:
       - YOLO-pose detecta personas y extrae keypoints en una sola pasada
       - Se toma la bbox con mayor confianza
       - Se extraen 17 landmarks COCO × (x, y) = 34 valores
       - Si YOLO falla → fila con keypoints NaN
  4. Guarda un CSV: keypoints_csv/video (i).csv

Columnas de salida (mismos nombres que el pipeline original con MediaPipe):
  frame, label,
  kp_0_x,  kp_0_y,   ← nose
  kp_1_x,  kp_1_y,   ← left eye
  kp_2_x,  kp_2_y,   ← right eye
  kp_7_x,  kp_7_y,   ← left ear
  kp_8_x,  kp_8_y,   ← right ear
  kp_11_x, kp_11_y,  ← left shoulder
  kp_12_x, kp_12_y,  ← right shoulder
  kp_13_x, kp_13_y,  ← left elbow
  kp_14_x, kp_14_y,  ← right elbow
  kp_15_x, kp_15_y,  ← left wrist
  kp_16_x, kp_16_y,  ← right wrist
  kp_23_x, kp_23_y,  ← left hip
  kp_24_x, kp_24_y,  ← right hip
  kp_25_x, kp_25_y,  ← left knee
  kp_26_x, kp_26_y,  ← right knee
  kp_27_x, kp_27_y,  ← left ankle
  kp_28_x, kp_28_y,  ← right ankle

Mapeo COCO (índice YOLO) → nombre columna CSV (nomenclatura MediaPipe):
  COCO 0  → kp_0   (nose)
  COCO 1  → kp_1   (left eye)
  COCO 2  → kp_2   (right eye)
  COCO 3  → kp_7   (left ear)
  COCO 4  → kp_8   (right ear)
  COCO 5  → kp_11  (left shoulder)
  COCO 6  → kp_12  (right shoulder)
  COCO 7  → kp_13  (left elbow)
  COCO 8  → kp_14  (right elbow)
  COCO 9  → kp_15  (left wrist)
  COCO 10 → kp_16  (right wrist)
  COCO 11 → kp_23  (left hip)
  COCO 12 → kp_24  (right hip)
  COCO 13 → kp_25  (left knee)
  COCO 14 → kp_26  (right knee)
  COCO 15 → kp_27  (left ankle)
  COCO 16 → kp_28  (right ankle)

Uso:
  python extract_keypoints_yolo_pose.py `
      --dataset_dir  "nombre_carpeta" `
      --model_path   "yolo11x-pose.pt" `
      [--conf        0.3] `
      [--iou         0.45] `
      [--img_size    640] `
      [--device      cuda:0] `
      [--output_dir  "ruta/salida"]
"""

import csv
import argparse
import numpy as np
import pandas as pd
from pathlib import Path

import cv2
from ultralytics import YOLO


# ──────────────────────────────────────────────────────────────────────────────
# Mapeo COCO → nombres de columna (nomenclatura MediaPipe original)
# Cada tupla: (índice COCO en YOLO-pose, nombre columna CSV)
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

# Columnas del CSV en orden
KP_COLS = [f"{name}_{dim}" for _, name in KEYPOINT_MAP for dim in ("x", "y")]

# Fila vacía cuando YOLO no detecta nada
EMPTY_KPS = [np.nan] * len(KP_COLS)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_video_files(videos_dir: Path) -> dict:
    return {p.stem: p for p in sorted(videos_dir.glob("*.avi"))}


def get_annotation_files(annotations_dir: Path) -> dict:
    return {p.stem: p for p in sorted(annotations_dir.glob("*.csv"))}


def load_label_map(csv_path: Path) -> dict:
    df = pd.read_csv(csv_path)
    return dict(zip(df["frame"].astype(int), df["label"].astype(int)))


def extract_keypoints(results) -> list:
    """
    Dado el resultado de YOLO-pose para un frame, extrae los keypoints
    de la persona con mayor confianza de bbox.
    Retorna lista de 34 floats (x, y por cada uno de los 17 landmarks)
    o EMPTY_KPS si no hay detección.
    """
    boxes = results[0].boxes
    kps_data = results[0].keypoints

    if boxes is None or len(boxes) == 0:
        return EMPTY_KPS
    if kps_data is None or len(kps_data.xy) == 0:
        return EMPTY_KPS

    best_idx = int(boxes.conf.argmax())
    xy = kps_data.xy[best_idx].cpu().numpy()   # shape (17, 2) — píxeles

    kps = []
    for coco_idx, _ in KEYPOINT_MAP:
        kps.append(float(xy[coco_idx, 0]))  # x
        kps.append(float(xy[coco_idx, 1]))  # y

    return kps


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────────────────────────────────────

def process_video(
    video_path: Path,
    label_map: dict,
    model: YOLO,
    conf: float,
    iou: float,
    img_size: int,
    device: str,
    normalize: bool,
) -> list:
    """
    Procesa un video frame a frame y retorna lista de dicts listos para CSV.
    Si normalize=True, las coordenadas x/y se dividen entre el ancho/alto
    del frame (valores 0–1), igual que hacía MediaPipe.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"    ⚠  No se pudo abrir: {video_path}")
        return []

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"    → {total_frames} frames | {fps:.1f} FPS | {frame_w}×{frame_h}px")

    rows = []
    frame_idx = 0

    while True:
        ret, frame_bgr = cap.read()
        if not ret:
            break

        frame_idx += 1
        label = label_map.get(frame_idx, -1)

        results = model(
            frame_bgr,
            conf=conf,
            iou=iou,
            imgsz=img_size,
            device=device,
            classes=[0],   # solo personas
            verbose=False,
        )

        kps = extract_keypoints(results)

        # Normalizar a [0, 1] igual que MediaPipe (opcional pero recomendado)
        if normalize and kps is not EMPTY_KPS:
            for i in range(0, len(kps), 2):
                if not np.isnan(kps[i]):
                    kps[i]     = kps[i]     / frame_w   # x
                    kps[i + 1] = kps[i + 1] / frame_h   # y

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
        print("    ⚠  Sin filas, no se guarda CSV.")
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
        description="Extrae keypoints por frame con YOLO11x-pose para el dataset LE2I."
    )
    parser.add_argument("--dataset_dir",  type=str, required=True,
                        help="Carpeta raíz del dataset (contiene Videos/ y annotations_csv/)")
    parser.add_argument("--model_path",   type=str, default="yolo11x-pose.pt",
                        help="Ruta al modelo YOLO-pose (.pt). Default: yolo11x-pose.pt")
    parser.add_argument("--conf",         type=float, default=0.3,
                        help="Umbral de confianza bbox. Default: 0.3")
    parser.add_argument("--iou",          type=float, default=0.45,
                        help="Umbral IoU NMS. Default: 0.45")
    parser.add_argument("--img_size",     type=int,   default=640,
                        help="Tamaño de inferencia YOLO. Default: 640")
    parser.add_argument("--device",       type=str,   default="cuda:0",
                        help="Dispositivo PyTorch. Default: cuda:0")
    parser.add_argument("--output_dir",   type=str,   default=None,
                        help="Carpeta de salida CSVs. Default: dataset_dir/keypoints_csv")
    parser.add_argument("--no_normalize", action="store_true",
                        help="Guardar coordenadas en píxeles (sin normalizar a [0,1])")
    args = parser.parse_args()

    dataset_dir     = Path(args.dataset_dir).resolve()
    annotations_dir = dataset_dir / "annotations_csv"
    videos_dir      = dataset_dir / "Videos"
    output_dir      = Path(args.output_dir).resolve() if args.output_dir else dataset_dir / "keypoints_csv"
    output_dir.mkdir(exist_ok=True)
    normalize       = not args.no_normalize

    for d, name in [(annotations_dir, "annotations_csv"), (videos_dir, "Videos")]:
        if not d.exists():
            raise FileNotFoundError(f"No se encontró '{name}' en: {dataset_dir}")

    print(f"\n📂 Dataset : {dataset_dir}")
    print(f"📤 Salida  : {output_dir}")
    print(f"📐 Normalizar coordenadas: {'Sí' if normalize else 'No (píxeles)'}\n")

    print("🔧 Cargando YOLO-pose...")
    model = YOLO(args.model_path)
    print("✅ Modelo cargado\n")

    video_files      = get_video_files(videos_dir)
    annotation_files = get_annotation_files(annotations_dir)
    common_stems     = sorted(set(video_files) & set(annotation_files))

    print(f"📄 Videos con anotación: {len(common_stems)}\n")

    for stem in common_stems:
        output_path = output_dir / f"{stem}.csv"

        if output_path.exists():
            print(f"  ⏭  Ya existe, saltando: {stem}.csv")
            continue

        print(f"🎬 [{stem}]")
        label_map = load_label_map(annotation_files[stem])

        rows = process_video(
            video_path=video_files[stem],
            label_map=label_map,
            model=model,
            conf=args.conf,
            iou=args.iou,
            img_size=args.img_size,
            device=args.device,
            normalize=normalize,
        )

        save_csv(rows, output_path)

        labels  = [r["label"] for r in rows]
        n_empty = sum(1 for r in rows if np.isnan(r.get(KP_COLS[0], np.nan)))
        print(
            f"    ✅ {output_path.name} | "
            f"frames: {len(rows)}  "
            f"(-1: {labels.count(-1)}, 0: {labels.count(0)}, 1: {labels.count(1)})  "
            f"sin_kps: {n_empty}\n"
        )

    print(f"✔  Pipeline completado. CSVs en:\n   {output_dir}")


if __name__ == "__main__":
    main()