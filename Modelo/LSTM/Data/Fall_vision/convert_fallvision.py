"""
Convierte los CSVs de FallVision al formato del pipeline LE2I.

Para cada CSV busca el video .mp4 correspondiente y usa su resolución
real para normalizar las coordenadas X,Y a [0,1].

Nombre de video correspondiente:
  S_D_0002_resized_keypoints.csv → S_D_0002_resized.mp4
  S_D_0006_keypoints.csv         → S_D_0006.mp4

Salida: un CSV por video con columnas:
  frame, label, kp_0_x, kp_0_y, kp_1_x, kp_1_y, ... kp_16_x, kp_16_y

Usar FEATURE_MODE="coco_xy" o "coco_xy_vel" en el notebook.

Uso:
  python convert_fallvision.py \
      --csv_dir    "FallVision/keypoints_csv" \
      --video_dir  "FallVision/videos" \
      --output_dir "FallVision/keypoints_converted" \
      [--fallback_width  512] \
      [--fallback_height 384]
"""

import cv2
import argparse
import numpy as np
import pandas as pd
from pathlib import Path


# Mapeo nombre COCO → índice MediaPipe
# Así los CSVs de FallVision quedan con las mismas columnas que LE2I
KEYPOINT_NAME_TO_IDX = {
    "Nose": 0,
    "Left Eye": 1,   "Right Eye": 2,
    "Left Ear": 7,   "Right Ear": 8,       # MediaPipe: 7,8
    "Left Shoulder": 11, "Right Shoulder": 12,
    "Left Elbow": 13,    "Right Elbow": 14,
    "Left Wrist": 15,    "Right Wrist": 16,
    "Left Hip": 23,      "Right Hip": 24,  # MediaPipe: 23,24
    "Left Knee": 25,     "Right Knee": 26,
    "Left Ankle": 27,    "Right Ankle": 28,
}

# Índices MediaPipe usados (equivalentes a COCO_INDICES del notebook)
MEDIAPIPE_INDICES = [0, 1, 2, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
N_KP = len(MEDIAPIPE_INDICES)


def get_video_resolution(video_path: Path):
    """Lee la resolución real del video .mp4."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None, None
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return w, h


def find_video(csv_path: Path, video_dir: Path):
    """
    Busca el video .mp4 correspondiente al CSV.
    S_D_0002_resized_keypoints.csv → S_D_0002_resized.mp4
    S_D_0006_keypoints.csv         → S_D_0006.mp4
    """
    stem = csv_path.stem  # ej: S_D_0002_resized_keypoints
    # Quitar sufijo _keypoints
    video_stem = stem.replace("_keypoints", "")
    for ext in (".mp4", ".avi", ".mov", ".mkv"):
        candidate = video_dir / (video_stem + ext)
        if candidate.exists():
            return candidate
    return None


def convert_csv(input_path: Path, width: float, height: float) -> pd.DataFrame:
    df = pd.read_csv(input_path)

    df["kp_idx"] = df["Keypoint"].map(KEYPOINT_NAME_TO_IDX)
    df = df.dropna(subset=["kp_idx"])
    df["kp_idx"] = df["kp_idx"].astype(int)

    # Si hay múltiples personas por frame, tomar solo las primeras 17 detecciones
    df = df.groupby("Frame").head(17).reset_index(drop=True)

    # Normalizar y clipar a [0, 1]
    df["X"] = (df["X"] / width).clip(0, 1)
    df["Y"] = (df["Y"] / height).clip(0, 1)

    rows = []
    for frame_num, group in df.groupby("Frame"):
        row = {"frame": int(frame_num), "label": 0}
        # Inicializar solo los índices MediaPipe que usamos
        for i in MEDIAPIPE_INDICES:
            row[f"kp_{i}_x"] = np.nan
            row[f"kp_{i}_y"] = np.nan
        for _, kp_row in group.iterrows():
            idx = int(kp_row["kp_idx"])  # ya es índice MediaPipe
            row[f"kp_{idx}_x"] = kp_row["X"]
            row[f"kp_{idx}_y"] = kp_row["Y"]
        rows.append(row)

    return pd.DataFrame(rows).sort_values("frame").reset_index(drop=True)


def main():
    parser = argparse.ArgumentParser(
        description="Convierte CSVs de FallVision al formato del pipeline LE2I."
    )
    parser.add_argument("--csv_dir",         type=str, required=True)
    parser.add_argument("--video_dir",        type=str, required=True)
    parser.add_argument("--output_dir",       type=str, required=True)
    parser.add_argument("--fallback_width",   type=float, default=512,
                        help="Ancho a usar si no se encuentra el video (default: 512)")
    parser.add_argument("--fallback_height",  type=float, default=384,
                        help="Alto a usar si no se encuentra el video (default: 384)")
    args = parser.parse_args()

    csv_dir    = Path(args.csv_dir)
    video_dir  = Path(args.video_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_files = sorted(csv_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No se encontraron CSVs en: {csv_dir}")

    print(f"\n📂 CSVs    : {csv_dir} ({len(csv_files)} archivos)")
    print(f"📂 Videos  : {video_dir}")
    print(f"📂 Salida  : {output_dir}\n")

    n_ok = 0
    n_fallback = 0

    for csv_path in csv_files:
        video_path = find_video(csv_path, video_dir)

        if video_path:
            w, h = get_video_resolution(video_path)
            if w and h:
                res_info = f"{w}×{h} (del video)"
                n_ok += 1
            else:
                w, h = args.fallback_width, args.fallback_height
                res_info = f"{w}×{h} (fallback)"
                n_fallback += 1
        else:
            w, h = args.fallback_width, args.fallback_height
            res_info = f"{w}×{h} (fallback, video no encontrado)"
            n_fallback += 1

        result = convert_csv(csv_path, w, h)
        out_path = output_dir / csv_path.name
        result.to_csv(out_path, index=False)

        n_frames = len(result)
        n_nan    = result["kp_0_x"].isna().sum()
        print(f"  ✅ {csv_path.name:45s} | {res_info} | {n_frames} frames (NaN:{n_nan})")

    print(f"\n{'─'*55}")
    print(f"✔  Total convertidos : {len(csv_files)}")
    print(f"   Con resolución real    : {n_ok}")
    print(f"   Con fallback           : {n_fallback}")
    print(f"\n⚠️  Usar FEATURE_MODE='coco_xy' o 'coco_xy_vel' en el notebook.")


if __name__ == "__main__":
    main()