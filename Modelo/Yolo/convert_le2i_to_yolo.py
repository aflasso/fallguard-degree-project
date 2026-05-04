import os
import cv2
import random
from glob import glob
from shutil import move

# ==============================
# CONFIGURACIÓN
# ==============================

BASE_PATH = r"C:\Users\andre\Desarrollo\Proyects\universidad\Proyecto de grado\Sistema\Modelo\Data\Le2i"
OUTPUT = r"C:\Users\andre\Desarrollo\Proyects\universidad\Proyecto de grado\Sistema\Modelo\Yolo\Data\Le2i_YOLO"

DATASETS = ["Coffee_room", "Home"]

# División del dataset
TRAIN_SPLIT = 0.80
VAL_SPLIT = 0.10
TEST_SPLIT = 0.10

CLASS_ID = 0   # Clase fija: persona

# ==============================
# FUNCIONES
# ==============================

def convert_to_yolo(xmin, ymin, xmax, ymax, img_w, img_h):
    """Convierte un bounding box a formato YOLO (normalizado)."""
    x_center = (xmin + xmax) / 2 / img_w
    y_center = (ymin + ymax) / 2 / img_h
    width = (xmax - xmin) / img_w
    height = (ymax - ymin) / img_h
    return x_center, y_center, width, height


def create_folders():
    """Crea las carpetas estándar YOLO."""
    for split in ["train", "val", "test"]:
        os.makedirs(os.path.join(OUTPUT, f"images/{split}"), exist_ok=True)
        os.makedirs(os.path.join(OUTPUT, f"labels/{split}"), exist_ok=True)


# ==============================
# SCRIPT PRINCIPAL
# ==============================

create_folders()

temp_images = []
temp_labels = []

print("\n=== INICIANDO CONVERSIÓN ===\n")

for dataset in DATASETS:
    print(f"\nProcesando carpeta: {dataset}")

    annotation_path = os.path.join(BASE_PATH, dataset, "Annotation_files")
    videos_path = os.path.join(BASE_PATH, dataset, "Videos")

    txt_files = glob(annotation_path + "/*.txt")

    for txt_file in txt_files:

        txt_name = os.path.basename(txt_file)
        video_name = txt_name.replace(".txt", ".avi")
        video_path = os.path.join(videos_path, video_name)

        if not os.path.exists(video_path):
            print(f"⚠ No se encontró video para {txt_name}")
            continue

        print(f"→ Procesando video: {video_name}")

        # Cargar anotaciones
        annotations = {}
        with open(txt_file, "r") as f:
            for line in f:
                line = line.strip()
                if "," in line:
                    frame, _, xmin, ymin, xmax, ymax = map(int, line.split(","))
                    annotations.setdefault(frame, []).append((xmin, ymin, xmax, ymax))

        cap = cv2.VideoCapture(video_path)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        frame_index = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_index += 1

            img_name = f"{dataset}_{video_name.replace('.avi','')}_{frame_index:05}.jpg"
            img_path = os.path.join(OUTPUT, "images/train", img_name)
            lbl_path = img_path.replace("images", "labels").replace(".jpg", ".txt")

            # Guardar imagen temporalmente en train (luego se moverá)
            cv2.imwrite(img_path, frame)
            temp_images.append(img_path)

            # Crear archivo de anotación
            with open(lbl_path, "w") as lf:
                if frame_index in annotations:
                    for xmin, ymin, xmax, ymax in annotations[frame_index]:

                        if xmin == 0 and ymin == 0 and xmax == 0 and ymax == 0:
                            continue

                        x_c, y_c, w_norm, h_norm = convert_to_yolo(
                            xmin, ymin, xmax, ymax, w, h
                        )
                        lf.write(f"{CLASS_ID} {x_c} {y_c} {w_norm} {h_norm}\n")

            temp_labels.append(lbl_path)

        cap.release()

# ==============================
# DIVISIÓN EN TRAIN / VAL / TEST
# ==============================

print("\n=== DIVIDIENDO DATASET ===")

all_items = list(zip(temp_images, temp_labels))
random.shuffle(all_items)

total = len(all_items)
train_end = int(total * TRAIN_SPLIT)
val_end = train_end + int(total * VAL_SPLIT)

splits = {
    "train": all_items[:train_end],
    "val": all_items[train_end:val_end],
    "test": all_items[val_end:]
}

for split, items in splits.items():
    print(f"{split}: {len(items)} imágenes")

    for img_path, lbl_path in items:
        new_img_path = img_path.replace("train", split)
        new_lbl_path = lbl_path.replace("train", split)

        move(img_path, new_img_path)
        move(lbl_path, new_lbl_path)

# ==============================
# CREAR data.yaml
# ==============================
yaml_path = os.path.join(OUTPUT, "data.yaml")

with open(yaml_path, "w") as f:
    f.write(
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n\n"
        "nc: 1\n"
        "names: ['person']\n"
    )

print("\n✔ CONVERSIÓN COMPLETA")
print(f"Dataset final generado en: {OUTPUT}")
