"""
Herramienta de anotación semi-automática para videos de caídas.

El video avanza automáticamente. Tú solo marcas inicio y fin de la caída.
Al terminar genera el .txt en el formato LE2I.

Controles:
  F        → marcar frame inicio de caída
  G        → marcar frame fin de caída
  ESPACIO  → pausar / reanudar
  R        → reiniciar video
  S        → guardar y pasar al siguiente video
  Q        → salir sin guardar

Uso:
  python annotator.py \
      --videos_dir   "Office/Videos" \
      --output_dir   "Office/Annotation_files" \
      [--fps_playback  25]   # velocidad de reproducción
      [--skip_existing]      # saltar videos que ya tienen .txt
"""

import cv2
import argparse
from pathlib import Path


def draw_hud(frame, frame_idx, total, fall_start, fall_end, paused):
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 70), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    # Barra de progreso
    progress = int((frame_idx / max(total, 1)) * w)
    cv2.rectangle(frame, (0, 65), (w, 70), (80, 80, 80), -1)
    cv2.rectangle(frame, (0, 65), (progress, 70), (0, 200, 100), -1)

    # Marcadores de caída en la barra
    if fall_start:
        fx = int((fall_start / total) * w)
        cv2.rectangle(frame, (fx - 2, 60), (fx + 2, 70), (0, 100, 255), -1)
    if fall_end:
        gx = int((fall_end / total) * w)
        cv2.rectangle(frame, (gx - 2, 60), (gx + 2, 70), (0, 50, 255), -1)

    # Texto
    state = "⏸ PAUSADO" if paused else "▶ PLAY"
    cv2.putText(frame, f"Frame: {frame_idx}/{total}  {state}",
                (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

    start_txt = f"F: inicio caida = {fall_start}" if fall_start else "F: marcar INICIO caida"
    end_txt   = f"G: fin caida    = {fall_end}"   if fall_end   else "G: marcar FIN caida"
    color_s = (0, 255, 100) if fall_start else (180, 180, 180)
    color_e = (0, 100, 255) if fall_end   else (180, 180, 180)

    cv2.putText(frame, start_txt, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_s, 1)
    cv2.putText(frame, end_txt,   (w//2, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_e, 1)

    # Instrucciones abajo
    cv2.rectangle(frame, (0, h - 28), (w, h), (0, 0, 0), -1)
    cv2.putText(frame, "F:inicio  G:fin  ESPACIO:pausa  R:reiniciar  S:guardar  Q:salir  ←/→:1f  A/D:10f",
                (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 180, 180), 1)

    return frame


def save_annotation(video_path, output_dir, fall_start, fall_end, total_frames, fps):
    """Genera el .txt en formato LE2I."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    txt_name = video_path.stem + ".txt"
    txt_path = output_dir / txt_name

    # Si no se marcó caída, todos los frames son actividad normal (0, 0)
    fs = fall_start or 0
    fe = fall_end   or 0

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"{fs}\n")
        f.write(f"{fe}\n")
        for i in range(1, total_frames + 1):
            # Columnas: frame, etiqueta_placeholder, 0, 0, 0, 0
            # (las columnas de bbox se dejan en 0 ya que no se usan en el pipeline)
            f.write(f"{i}, 0, 0, 0, 0, 0\n")

    return txt_path


def annotate_video(video_path, output_dir, fps_playback, skip_existing):
    output_dir = Path(output_dir)
    txt_path = output_dir / (video_path.stem + ".txt")

    if skip_existing and txt_path.exists():
        print(f"  ⏭  Ya existe, saltando: {video_path.name}")
        return True

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"  ⚠️  No se pudo abrir: {video_path.name}")
        return False

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    native_fps   = cap.get(cv2.CAP_PROP_FPS) or 25.0
    delay_ms     = max(1, int(1000 / fps_playback))

    print(f"\n🎬 {video_path.name}  ({total_frames} frames, {native_fps:.0f}fps)")

    # Cargar todos los frames en memoria (videos cortos ~3s)
    frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()

    total_frames = len(frames)
    fall_start = None
    fall_end   = None
    frame_idx  = 0
    paused     = False

    cv2.namedWindow("Anotador", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Anotador", 800, 600)

    while True:
        display = frames[frame_idx].copy()
        display = draw_hud(display, frame_idx + 1, total_frames,
                           fall_start, fall_end, paused)
        cv2.imshow("Anotador", display)

        wait = 0 if paused else delay_ms
        key  = cv2.waitKey(wait) & 0xFF

        if key == ord('q'):
            cv2.destroyAllWindows()
            return False  # señal de salir completamente

        elif key == ord('s'):
            # Guardar y continuar con el siguiente
            saved = save_annotation(video_path, output_dir,
                                    fall_start, fall_end, total_frames, native_fps)
            fs = fall_start or 0
            fe = fall_end   or 0
            print(f"  ✅ Guardado: {saved.name}  (inicio={fs}, fin={fe})")
            break

        elif key == ord('f'):
            fall_start = frame_idx + 1
            print(f"     📍 Inicio caída marcado: frame {fall_start}")

        elif key == ord('g'):
            fall_end = frame_idx + 1
            print(f"     📍 Fin caída marcado: frame {fall_end}")

        elif key == ord(' '):
            paused = not paused

        elif key == ord('r'):
            frame_idx = 0
            fall_start = None
            fall_end   = None
            paused     = True
            print("     🔄 Reiniciado")

        elif key == 83 or key == ord('d'):   # → o D → avanzar 10 frames
            frame_idx = min(frame_idx + 10, total_frames - 1)
            paused = True

        elif key == 81 or key == ord('a'):   # ← o A → retroceder 10 frames
            frame_idx = max(frame_idx - 10, 0)
            paused = True

        elif key == 82:                      # ↑ → avanzar 1 frame
            frame_idx = min(frame_idx + 1, total_frames - 1)
            paused = True

        elif key == 84:                      # ↓ → retroceder 1 frame
            frame_idx = max(frame_idx - 1, 0)
            paused = True

        # Avanzar frame si no está pausado
        if not paused:
            frame_idx = min(frame_idx + 1, total_frames - 1)
            if frame_idx == total_frames - 1:
                paused = True  # pausar al llegar al final

    cv2.destroyAllWindows()
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Anotador semi-automático de caídas para dataset LE2I."
    )
    parser.add_argument("--videos_dir",    type=str, required=True,
                        help="Carpeta con los videos .avi")
    parser.add_argument("--output_dir",    type=str, required=True,
                        help="Carpeta donde guardar los .txt de anotaciones")
    parser.add_argument("--fps_playback",  type=int, default=25,
                        help="Velocidad de reproducción en FPS (default: 25)")
    parser.add_argument("--skip_existing", action="store_true",
                        help="Saltar videos que ya tienen .txt")
    args = parser.parse_args()

    videos_dir = Path(args.videos_dir)
    video_files = sorted([
        p for p in videos_dir.glob("*.avi")
    ])

    if not video_files:
        raise FileNotFoundError(f"No se encontraron .avi en: {videos_dir}")

    print(f"\n📂 Videos    : {videos_dir} ({len(video_files)} archivos)")
    print(f"📂 Salida    : {args.output_dir}")
    print(f"⚙️  Velocidad : {args.fps_playback} FPS\n")
    print("Controles:")
    print("  F        → marcar inicio de caída")
    print("  G        → marcar fin de caída")
    print("  ESPACIO  → pausar / reanudar")
    print("  R        → reiniciar video")
    print("  S        → guardar y pasar al siguiente")
    print("  Q        → salir\n")

    for i, video_path in enumerate(video_files):
        print(f"[{i+1}/{len(video_files)}]", end=" ")
        cont = annotate_video(
            video_path=video_path,
            output_dir=args.output_dir,
            fps_playback=args.fps_playback,
            skip_existing=args.skip_existing,
        )
        if not cont:
            print("\n⏹  Anotación interrumpida.")
            break

    print(f"\n✔  Sesión terminada. Anotaciones en: {args.output_dir}")


if __name__ == "__main__":
    main()