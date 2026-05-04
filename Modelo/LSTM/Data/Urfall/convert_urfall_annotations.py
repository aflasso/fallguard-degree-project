"""
Convierte el archivo de anotaciones de URFALL (urfall-cam0-falls.csv)
a CSVs individuales por video en el formato del pipeline LE2I.

Formato entrada (urfall-cam0-falls.csv):
  video_name, frame, label(-1/0/1), ...otras columnas...

Formato salida (annotations_csv/fall-01.csv):
  frame, label

Uso:
  python convert_urfall_annotations.py \
      --input_csv  "URFALL/urfall-cam0-falls.csv" \
      --output_dir "URFALL/annotations_csv"
"""

import argparse
import pandas as pd
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Convierte anotaciones URFALL a CSVs por video."
    )
    parser.add_argument("--input_csv",  type=str, required=True,
                        help="Ruta al archivo urfall-cam0-falls.csv")
    parser.add_argument("--output_dir", type=str, required=True,
                        help="Carpeta de salida para los CSVs por video")
    args = parser.parse_args()

    input_csv  = Path(args.input_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Leer sin header — columnas: 0=video, 1=frame, 2=label, resto ignorado
    df = pd.read_csv(input_csv, header=None)
    df = df.rename(columns={0: "video", 1: "frame", 2: "label"})
    df = df[["video", "frame", "label"]]

    videos = df["video"].unique()
    print(f"\n📄 Archivo  : {input_csv}")
    print(f"📂 Salida   : {output_dir}")
    print(f"🎬 Videos   : {len(videos)}\n")

    for video_name in sorted(videos):
        video_df = df[df["video"] == video_name][["frame", "label"]].reset_index(drop=True)
        out_path = output_dir / f"{video_name}.csv"
        video_df.to_csv(out_path, index=False)

        n_normal = (video_df["label"] == -1).sum()
        n_fall   = (video_df["label"] ==  0).sum()
        n_post   = (video_df["label"] ==  1).sum()
        print(f"  ✅ {video_name:15s} → {out_path.name}  "
              f"frames: {len(video_df):4d}  "
              f"(-1: {n_normal:3d}, 0: {n_fall:3d}, 1: {n_post:3d})")

    print(f"\n✔  {len(videos)} CSVs generados en: {output_dir}")


if __name__ == "__main__":
    main()