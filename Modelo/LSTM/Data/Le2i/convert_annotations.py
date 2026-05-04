"""
Convierte los archivos de anotación .txt del dataset LE2I a CSV normalizados.

Etiquetas de salida:
  -1 → actividad normal (frames antes de la caída)
   0 → caída en progreso (frames dentro del intervalo)
   1 → post-caída / persona en el piso (frames después del intervalo)

Si ambas primeras líneas son 0 o no existen, todos los frames → -1.

Uso:
    python convert_annotations.py --input_dir "nombre_carpeta/Annotation_files"

El script crea automáticamente:
    nombre_carpeta/annotations_csv/video (N).csv
"""

import os
import re
import csv
import argparse


def parse_annotation_file(filepath: str):
    """
    Lee un archivo .txt de LE2I y retorna una lista de (frame_num, label).

    Formato esperado del archivo:
        Línea 1: frame_inicio_caida
        Línea 2: frame_fin_caida
        Líneas siguientes: frame_num, col2, col3, col4, col5, col6
    """
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = [l.rstrip("\n").strip() for l in f.readlines()]

    # Separar las primeras dos líneas de las líneas de frames
    # Una línea de frame tiene al menos una coma (6 columnas)
    # Una línea de cabecera es solo un número entero
    header_lines = []
    frame_lines = []

    for line in lines:
        if not line:
            continue
        if "," in line:
            frame_lines.append(line)
        else:
            # Es un número suelto (cabecera)
            if len(header_lines) < 2:
                header_lines.append(line)
            else:
                # Si hay más números sueltos después de los 2 de cabecera,
                # podrían ser frames con formato diferente; los ignoramos.
                pass

    # Determinar intervalo de caída
    fall_start = None
    fall_end = None
    try:
        if len(header_lines) >= 2:
            fall_start = int(header_lines[0])
            fall_end = int(header_lines[1])
    except ValueError:
        fall_start = None
        fall_end = None

    # Si ambos son 0 o no hay cabecera válida → todos son actividad normal
    all_normal = (fall_start is None) or (fall_start == 0 and fall_end == 0)

    records = []
    for line in frame_lines:
        parts = line.split(",")
        try:
            frame_num = int(parts[0].strip())
        except (ValueError, IndexError):
            continue  # línea malformada, se omite

        if all_normal:
            label = -1
        else:
            if frame_num < fall_start:
                label = -1
            elif fall_start <= frame_num <= fall_end:
                label = 0
            else:
                label = 1

        records.append((frame_num, label))

    return records


def convert_folder(input_dir: str):
    """
    Procesa todos los .txt en input_dir y guarda CSV en la carpeta
    annotations_csv al mismo nivel que input_dir.
    """
    input_dir = os.path.abspath(input_dir)
    parent_dir = os.path.dirname(input_dir)
    output_dir = os.path.join(parent_dir, "annotations_csv")
    os.makedirs(output_dir, exist_ok=True)

    txt_files = sorted(
        [f for f in os.listdir(input_dir) if f.lower().endswith(".txt")]
    )

    if not txt_files:
        print(f"⚠  No se encontraron archivos .txt en: {input_dir}")
        return

    print(f"📂 Carpeta de entrada : {input_dir}")
    print(f"📂 Carpeta de salida  : {output_dir}")
    print(f"📄 Archivos encontrados: {len(txt_files)}\n")

    for txt_file in txt_files:
        txt_path = os.path.join(input_dir, txt_file)

        # Nombre del CSV: mismo nombre base, extensión .csv
        base_name = os.path.splitext(txt_file)[0]  # e.g. "video (1)"
        csv_filename = base_name + ".csv"
        csv_path = os.path.join(output_dir, csv_filename)

        try:
            records = parse_annotation_file(txt_path)
        except Exception as e:
            print(f"  ❌ Error procesando '{txt_file}': {e}")
            continue

        with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["frame", "label"])
            writer.writerows(records)

        # Resumen rápido por archivo
        labels = [r[1] for r in records]
        n_normal = labels.count(-1)
        n_fall   = labels.count(0)
        n_post   = labels.count(1)
        print(
            f"  ✅ {txt_file:30s} → {csv_filename:30s} "
            f"| frames: {len(records):4d}  "
            f"(-1: {n_normal:4d}, 0: {n_fall:4d}, 1: {n_post:4d})"
        )

    print(f"\n✔  Conversión completada. CSVs guardados en:\n   {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convierte anotaciones LE2I (.txt) a CSV normalizados."
    )
    parser.add_argument(
        "--input_dir",
        type=str,
        required=True,
        help='Ruta a la carpeta Annotation_files, ej: "mi_dataset/Annotation_files"',
    )
    args = parser.parse_args()
    convert_folder(args.input_dir)