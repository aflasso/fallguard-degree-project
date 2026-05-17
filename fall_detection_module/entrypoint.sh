#!/bin/sh
# Convierte el video fuente a mp4/h264 si es necesario.
# opencv-python-headless no puede decodificar todos los codecs de .avi
# (ej: DIVX del dataset LE2I). El ffmpeg del sistema sí puede.

SOURCE="${CAMERA_SOURCE:-0}"

# Solo convertir si es un archivo de video (no índice de cámara)
case "$SOURCE" in
  *.avi|*.AVI|*.mkv|*.MKV|*.wmv|*.WMV)
    CONVERTED="/tmp/test_video.mp4"
    echo "[entrypoint] Convirtiendo '$SOURCE' → '$CONVERTED'..."
    ffmpeg -y -loglevel warning -i "$SOURCE" \
      -c:v libx264 -preset ultrafast -crf 0 \
      -an "$CONVERTED"
    if [ $? -eq 0 ]; then
      echo "[entrypoint] Conversión exitosa"
      export CAMERA_SOURCE="$CONVERTED"
    else
      echo "[entrypoint] Error convirtiendo video — usando fuente original"
    fi
    ;;
esac

exec python main.py
