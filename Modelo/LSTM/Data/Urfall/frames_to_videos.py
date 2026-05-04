"""
Convierte carpetas de imágenes (frames) a videos .avi.

Cada carpeta se convierte en un video con el mismo nombre.
Útil para procesar el dataset URFALL con el pipeline existente.

Estructura esperada:
  input_dir/
    fall-01/
      fall-01-cam0-rgb-001.png
      fall-01-cam0-rgb-002.png
      ...
    fall-02/
      ...

Salida:
  output_dir/
    fall-01.avi
    fall-02.avi
    ...

Uso:
  python frames_to_videos.py \
      --input_dir  "URFALL/frames" \
      --output_dir "URFALL/Videos" \
      [--fps       25] \
      [--ext       png]
"""

import cv2
import argparse
import numpy as np
from pathlib import Path


def frames_to_video(frames_dir: Path, output_path: Path, fps: int, ext: str):
    frames = sorted(frames_dir.glob(f"*.{ext}"))
    if not frames:
        return 0

    first = cv2.imread(str(frames[0]))
    if first is None:
        return 0

    h, w = first.shape[:2]
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"XVID"),
        fps, (w, h)
    )

    for frame_path in frames:
        img = cv2.imread(str(frame_path))
        if img is not None:
            writer.write(img)

    writer.release()
    return len(frames)


def main():
    parser = argparse.ArgumentParser(
        description="Convierte carpetas de imágenes a videos .avi."
    )
    parser.add_argument("--input_dir",  type=str, required=True,
                        help="Carpeta raíz con subcarpetas de frames")
    parser.add_argument("--output_dir", type=str, required=True,
                        help="Carpeta de salida para los videos .avi")
    parser.add_argument("--fps", type=int, default=25,
                        help="FPS del video de salida (default: 25)")
    parser.add_argument("--ext", type=str, default="png",
                        help="Extensión de las imágenes (default: png)")
    args = parser.parse_args()

    input_dir  = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Buscar todas las subcarpetas
    folders = sorted([f for f in input_dir.iterdir() if f.is_dir()])
    if not folders:
        raise FileNotFoundError(f"No se encontraron subcarpetas en: {input_dir}")

    print(f"\n📂 Entrada : {input_dir} ({len(folders)} carpetas)")
    print(f"📂 Salida  : {output_dir}")
    print(f"⚙️  FPS: {args.fps} | Extensión: .{args.ext}\n")

    for folder in folders:
        output_path = output_dir / f"{folder.name}.avi"

        if output_path.exists():
            print(f"  ⏭  Ya existe, saltando: {output_path.name}")
            continue

        n_frames = frames_to_video(folder, output_path, args.fps, args.ext)

        if n_frames == 0:
            print(f"  ⚠️  Sin imágenes: {folder.name}")
        else:
            print(f"  ✅ {folder.name:30s} → {output_path.name}  ({n_frames} frames)")

    print(f"\n✔  Conversión completada. Videos en: {output_dir}")


if __name__ == "__main__":
    main()