"""
Evaluación de métricas a nivel de evento para detección de caídas.

Estructura esperada de carpetas:
    dataset_dir/
    ├── Fall/    <- videos CON caída  (exactamente 1 caída esperada por video)
    └── NFall/   <- videos SIN caída  (0 caídas esperadas)

Lógica de conteo:
    - Un "evento" es un grupo de frames consecutivos con predicción de caída,
      separados por al menos MIN_SILENCE frames sin caída.
    - Video Fall  con N eventos detectados -> 1 TP + (N-1) FP  (si N >= 1)
    - Video Fall  con 0 eventos            -> 1 FN
    - Video NFall con N eventos detectados -> N FP
    - Video NFall con 0 eventos            -> 1 TN

Métricas:
    Precision = TP / (TP + FP)
    Recall    = TP / (TP + FN)
    F1        = 2 * P * R / (P + R)

    Micro average: suma TP/FP/FN de todos los datasets y calcula una vez
    Macro average: promedia las métricas individuales de cada dataset

Uso — un dataset:
    python evaluate_videos.py ^
        --dataset_dirs "Lecture_room" ^
        --model_path   "lstm_data/fall_lstm_final.pt" ^
        --yolo_path    "yolo11x-pose.pt" ^
        [--conf        0.1] ^
        [--conf_lstm   0.0] ^
        [--device      cuda:0] ^
        [--min_frames  3] ^
        [--min_silence 10]

Uso — varios datasets:
    python evaluate_videos.py ^
        --dataset_dirs "Lecture_room" "Office" ^
        --model_path   "lstm_data/fall_lstm_final.pt" ^
        --yolo_path    "yolo11x-pose.pt"
"""

import csv
import cv2
import argparse
import numpy as np
import torch
import torch.nn as nn
from collections import deque
from pathlib import Path

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
    (0,  "kp_0"),   (1,  "kp_1"),   (2,  "kp_2"),
    (3,  "kp_7"),   (4,  "kp_8"),
    (5,  "kp_11"),  (6,  "kp_12"),
    (7,  "kp_13"),  (8,  "kp_14"),
    (9,  "kp_15"),  (10, "kp_16"),
    (11, "kp_23"),  (12, "kp_24"),
    (13, "kp_25"),  (14, "kp_26"),
    (15, "kp_27"),  (16, "kp_28"),
]
COCO_INDICES = [coco_idx for coco_idx, _ in KEYPOINT_MAP]


# ──────────────────────────────────────────────────────────────────────────────
# Features: coco_xy_vel -> x,y (34) + velocidad x,y (34) = 68 features/frame
# ──────────────────────────────────────────────────────────────────────────────
def extract_keypoints(results):
    boxes    = results[0].boxes
    kps_data = results[0].keypoints
    if boxes is None or len(boxes) == 0:
        return None
    if kps_data is None or len(kps_data.xyn) == 0:
        return None
    best_idx = int(boxes.conf.argmax())
    xyn = kps_data.xyn[best_idx].cpu().numpy()
    kps = np.zeros(len(COCO_INDICES) * 2, dtype=np.float32)
    for map_idx, coco_idx in enumerate(COCO_INDICES):
        kps[map_idx * 2]     = xyn[coco_idx, 0]
        kps[map_idx * 2 + 1] = xyn[coco_idx, 1]
    return kps


def build_features(buffer):
    arr = np.array(buffer, dtype=np.float32)
    vel = np.zeros_like(arr)
    vel[1:] = arr[1:] - arr[:-1]
    return np.concatenate([arr, vel], axis=1)


# ──────────────────────────────────────────────────────────────────────────────
# Detección de eventos con confianza
# ──────────────────────────────────────────────────────────────────────────────
def extract_fall_events(frame_preds, frame_confs, min_frames, min_silence):
    events        = []
    in_fall       = False
    event_start   = 0
    event_end     = 0
    fall_count    = 0
    silence       = 0
    current_confs = []

    for i, (lbl, conf) in enumerate(zip(frame_preds, frame_confs)):
        if lbl == 1:
            if not in_fall:
                in_fall       = True
                event_start   = i
                silence       = 0
                fall_count    = 0
                current_confs = []
            else:
                silence = 0
            event_end = i
            fall_count += 1
            current_confs.append(conf)
        else:
            if in_fall:
                silence += 1
                if silence >= min_silence:
                    if fall_count >= min_frames:
                        events.append({
                            "frame_inicio": event_start,
                            "frame_fin":    event_end,
                            "duracion":     fall_count,
                            "conf_max":     round(float(np.max(current_confs)), 4),
                            "conf_media":   round(float(np.mean(current_confs)), 4),
                        })
                    in_fall       = False
                    fall_count    = 0
                    silence       = 0
                    current_confs = []

    if in_fall and fall_count >= min_frames:
        events.append({
            "frame_inicio": event_start,
            "frame_fin":    event_end,
            "duracion":     fall_count,
            "conf_max":     round(float(np.max(current_confs)), 4),
            "conf_media":   round(float(np.mean(current_confs)), 4),
        })

    return events


# ──────────────────────────────────────────────────────────────────────────────
# Procesar un video
# ──────────────────────────────────────────────────────────────────────────────
def process_video(video_path, yolo, lstm_model, window, device, conf_yolo):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"    ⚠  No se pudo abrir: {video_path.name}")
        return [], []

    kp_buffer   = deque(maxlen=window)
    frame_preds = []
    frame_confs = []
    MAX_MISSING = 10
    missing     = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results   = yolo(frame, conf=conf_yolo, device=device, verbose=False)
        kps_frame = extract_keypoints(results)

        if kps_frame is not None:
            missing = 0
            kp_buffer.append(kps_frame)

            if len(kp_buffer) == window:
                features = build_features(list(kp_buffer))
                X = torch.tensor(features, dtype=torch.float32).unsqueeze(0).to(device)
                with torch.no_grad():
                    logits     = lstm_model(X)
                    probs      = torch.softmax(logits, dim=1)[0].cpu().numpy()
                    pred       = int(np.argmax(probs))
                    prob_caida = float(probs[1])
                frame_preds.append(pred)
                frame_confs.append(prob_caida)
            else:
                frame_preds.append(0)
                frame_confs.append(0.0)
        else:
            missing += 1
            if missing > MAX_MISSING:
                kp_buffer.clear()
            frame_preds.append(0)
            frame_confs.append(0.0)

    cap.release()
    return frame_preds, frame_confs


# ──────────────────────────────────────────────────────────────────────────────
# Calcular métricas desde TP/FP/FN
# ──────────────────────────────────────────────────────────────────────────────
def calc_metrics(tp, fp, fn):
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


# ──────────────────────────────────────────────────────────────────────────────
# Evaluar un dataset completo
# ──────────────────────────────────────────────────────────────────────────────
def evaluate_dataset(dataset_dir, yolo, lstm, window, device, args):
    fall_dir  = dataset_dir / "Fall"
    nfall_dir = dataset_dir / "NFall"

    for d in [fall_dir, nfall_dir]:
        if not d.exists():
            raise FileNotFoundError(f"No se encontró: {d}")

    VIDEO_EXTS  = {".avi", ".mp4", ".mov", ".mkv"}
    TP = FP = FN = TN = 0
    results_log = []
    events_log  = []

    for is_fall, folder, label_str in [(True, fall_dir, "Fall"), (False, nfall_dir, "NFall")]:
        videos = [p for p in sorted(folder.iterdir()) if p.suffix.lower() in VIDEO_EXTS]
        print(f"  📂 {label_str}/ — {len(videos)} videos")

        for vpath in videos:
            print(f"    🎬 {vpath.name} ...", end=" ", flush=True)

            preds, confs = process_video(vpath, yolo, lstm, window, device, args.conf)
            events       = extract_fall_events(preds, confs, args.min_frames, args.min_silence)

            if args.conf_lstm > 0:
                events = [e for e in events if e["conf_media"] >= args.conf_lstm]
            n_events = len(events)

            fall_frames = sum(1 for p in preds if p == 1)
            fall_pct    = fall_frames / max(len(preds), 1) * 100

            conf_max_video = round(max(confs), 4) if confs else 0.0
            if events:
                conf_max_eventos   = round(max(e["conf_max"]  for e in events), 4)
                conf_media_eventos = round(float(np.mean([e["conf_media"] for e in events])), 4)
            else:
                conf_max_eventos   = 0.0
                conf_media_eventos = 0.0

            if is_fall:
                if n_events >= 1:
                    tp_inc = 1
                    fp_inc = n_events - 1
                    fn_inc = 0
                    verdict = "✅ TP" + (f" + {fp_inc} FP extra" if fp_inc > 0 else "")
                else:
                    tp_inc = 0
                    fp_inc = 0
                    fn_inc = 1
                    verdict = "❌ FN (no detectó)"
            else:
                tp_inc = 0
                fp_inc = n_events
                fn_inc = 0
                if n_events == 0:
                    TN += 1
                    verdict = "✅ TN"
                else:
                    verdict = f"❌ FP x{n_events}"

            TP += tp_inc
            FP += fp_inc
            FN += fn_inc

            print(f"{verdict}  |  eventos={n_events}  "
                  f"frames_caida={fall_pct:.1f}%  "
                  f"conf_max={conf_max_eventos:.3f}  "
                  f"conf_media={conf_media_eventos:.3f}")

            results_log.append({
                "dataset":             dataset_dir.name,
                "video":               vpath.name,
                "tipo":                label_str,
                "eventos":             n_events,
                "frames_caida_pct":    round(fall_pct, 1),
                "conf_max_video":      conf_max_video,
                "conf_max_eventos":    conf_max_eventos,
                "conf_media_eventos":  conf_media_eventos,
                "TP": tp_inc, "FP": fp_inc, "FN": fn_inc,
                "verdict":             verdict,
            })

            for ev_idx, ev in enumerate(events):
                events_log.append({
                    "dataset":      dataset_dir.name,
                    "video":        vpath.name,
                    "tipo":         label_str,
                    "evento_num":   ev_idx + 1,
                    "frame_inicio": ev["frame_inicio"],
                    "frame_fin":    ev["frame_fin"],
                    "duracion":     ev["duracion"],
                    "conf_max":     ev["conf_max"],
                    "conf_media":   ev["conf_media"],
                })

        print()

    precision, recall, f1 = calc_metrics(TP, FP, FN)

    print(f"  {'─'*45}")
    print(f"  TP:{TP:4d}  FP:{FP:4d}  FN:{FN:4d}  TN:{TN:4d}")
    print(f"  Precision:{precision:.4f}  Recall:{recall:.4f}  F1:{f1:.4f}")
    print()

    return {
        "TP": TP, "FP": FP, "FN": FN, "TN": TN,
        "precision": precision, "recall": recall, "f1": f1,
        "results_log": results_log,
        "events_log":  events_log,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Evaluación por evento — detección de caídas.")
    parser.add_argument("--dataset_dirs", type=str, nargs="+", required=True,
                        help="Una o más carpetas con subcarpetas Fall/ y NFall/")
    parser.add_argument("--model_path",   type=str, required=True)
    parser.add_argument("--yolo_path",    type=str, required=True)
    parser.add_argument("--conf",         type=float, default=0.8,
                        help="Confianza minima de YOLO para detectar persona. Default: 0.1")
    parser.add_argument("--conf_lstm",    type=float, default=0.0,
                        help="Umbral minimo de conf_media del evento. Default: 0.0 (sin umbral)")
    parser.add_argument("--device",       type=str,   default="cuda:0")
    parser.add_argument("--min_frames",   type=int,   default=3,
                        help="Frames minimos con caida para contar un evento. Default: 3")
    parser.add_argument("--min_silence",  type=int,   default=10,
                        help="Frames de silencio para separar eventos. Default: 10")
    parser.add_argument("--output_dir",   type=str,   default=None,
                        help="Carpeta donde guardar los CSVs. Default: carpeta del dataset (1 dataset) o directorio actual (varios)")
    args = parser.parse_args()

    # ── Cargar modelos ────────────────────────────────────────────────────
    checkpoint = torch.load(args.model_path, map_location="cpu")
    hp         = checkpoint["hyperparams"]
    window     = hp["window"]

    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    lstm   = FallLSTM(
        input_size=hp["input_size"],
        hidden_size=hp["hidden_size"],
        num_layers=hp["num_layers"],
        num_classes=hp["num_classes"],
        dropout=hp["dropout"],
    ).to(device)
    lstm.load_state_dict(checkpoint["model_state_dict"])
    lstm.eval()
    print(f"✅ LSTM cargado | ventana={window} | features={hp['input_size']}")

    yolo = YOLO(args.yolo_path)
    print(f"✅ YOLO-pose cargado")
    print(f"   conf_yolo={args.conf}  conf_lstm={args.conf_lstm if args.conf_lstm > 0 else 'sin umbral'}"
          f"  min_frames={args.min_frames}  min_silence={args.min_silence}\n")

    # ── Evaluar cada dataset ──────────────────────────────────────────────
    dataset_results = {}
    all_results_log = []
    all_events_log  = []

    for ddir in args.dataset_dirs:
        dataset_dir = Path(ddir)
        print(f"{'='*55}")
        print(f"📂 Dataset: {dataset_dir.name}")
        print(f"{'='*55}")

        res = evaluate_dataset(dataset_dir, yolo, lstm, window, device, args)
        dataset_results[dataset_dir.name] = res
        all_results_log.extend(res["results_log"])
        all_events_log.extend(res["events_log"])

    # ── Métricas combinadas (solo si hay más de un dataset) ───────────────
    if len(args.dataset_dirs) > 1:
        print(f"{'='*55}")
        print("📊 MÉTRICAS COMBINADAS")
        print(f"{'='*55}")

        # Micro average
        micro_tp = sum(r["TP"] for r in dataset_results.values())
        micro_fp = sum(r["FP"] for r in dataset_results.values())
        micro_fn = sum(r["FN"] for r in dataset_results.values())
        micro_tn = sum(r["TN"] for r in dataset_results.values())
        micro_p, micro_r, micro_f1 = calc_metrics(micro_tp, micro_fp, micro_fn)

        # Macro average
        macro_p  = float(np.mean([r["precision"] for r in dataset_results.values()]))
        macro_r  = float(np.mean([r["recall"]    for r in dataset_results.values()]))
        macro_f1 = float(np.mean([r["f1"]        for r in dataset_results.values()]))

        print(f"\n  Por dataset:")
        for name, r in dataset_results.items():
            print(f"    {name:20s} P:{r['precision']:.4f}  R:{r['recall']:.4f}  F1:{r['f1']:.4f}"
                  f"  (TP:{r['TP']} FP:{r['FP']} FN:{r['FN']} TN:{r['TN']})")

        print(f"\n  Micro average  (TP:{micro_tp} FP:{micro_fp} FN:{micro_fn} TN:{micro_tn})")
        print(f"    Precision : {micro_p:.4f}")
        print(f"    Recall    : {micro_r:.4f}")
        print(f"    F1        : {micro_f1:.4f}")

        print(f"\n  Macro average")
        print(f"    Precision : {macro_p:.4f}")
        print(f"    Recall    : {macro_r:.4f}")
        print(f"    F1        : {macro_f1:.4f}")
        print(f"{'='*55}")

    # ── Guardar logs ──────────────────────────────────────────────────────
    # Determinar carpeta de salida
    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
    elif len(args.dataset_dirs) == 1:
        out_dir = Path(args.dataset_dirs[0])
    else:
        out_dir = Path(".")

    summary_path = out_dir / "evaluation_results.csv"
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_results_log[0].keys())
        writer.writeheader()
        writer.writerows(all_results_log)
    print(f"\n📄 Resumen por video : {summary_path}")

    if all_events_log:
        events_path = out_dir / "evaluation_events.csv"
        with open(events_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=all_events_log[0].keys())
            writer.writeheader()
            writer.writerows(all_events_log)
        print(f"📄 Detalle por evento: {events_path}")
    else:
        print("⚠  No se detectó ningún evento — evaluation_events.csv no generado.")


if __name__ == "__main__":
    main()