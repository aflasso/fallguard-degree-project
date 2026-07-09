"""
Infraestructura — implementación del ClipRecorder.
Implementa el puerto application/ports/clip_recorder.py

Mantiene un buffer circular de frames BGR en memoria.
Cuando se confirma una caída:
  1. Toma context_before frames del buffer (ya capturados)
  2. Sigue capturando context_after frames adicionales
  3. Graba todo como .mp4
  4. Llama al callback on_ready(clip_path)
"""

import cv2
import logging
import os
import threading
from collections import deque
from typing import Callable, Optional

import numpy as np

from domain.entities import FallEvent
from application.ports.clip_recorder import ClipRecorder

logger = logging.getLogger(__name__)


class OpenCVClipRecorder(ClipRecorder):
    """
    Implementa ClipRecorder usando OpenCV VideoWriter.

    Mantiene un buffer circular de frames en memoria — siempre
    tiene los últimos context_before frames disponibles.
    Cuando recibe record(), espera context_after frames adicionales
    antes de cerrar el archivo.
    """

    def __init__(
        self,
        clips_dir:      str = "clips",
        context_before: int = 75,    # ~3s a 25fps
        context_after:  int = 50,    # ~2s a 25fps
        fps:            float = 25.0,
    ):
        self._clips_dir      = clips_dir
        self._context_before = context_before
        self._context_after  = context_after
        self._fps            = fps

        # Buffer circular — siempre tiene los últimos context_before frames
        self._buffer: deque = deque(maxlen=context_before)

        # Estado de grabación
        self._recording:        bool                    = False
        self._frames_after:     int                     = 0
        self._writer:           Optional[cv2.VideoWriter] = None
        self._on_ready:         Optional[Callable]      = None
        self._current_clip_path: Optional[str]          = None
        self._lock = threading.Lock()

        os.makedirs(clips_dir, exist_ok=True)

    # ── Puerto ────────────────────────────────────────────────────────────

    def add_frame(self, frame: np.ndarray) -> None:
        """
        Agrega un frame al buffer circular.
        Si hay grabación en curso también lo escribe al archivo.
        """
        with self._lock:
            self._buffer.append(frame.copy())

            if self._recording and self._writer is not None:
                self._writer.write(frame)
                self._frames_after += 1

                if self._frames_after >= self._context_after:
                    self._finish_recording()

    def record(
        self,
        event:    FallEvent,
        on_ready: Callable[[str], None],
    ) -> None:
        """
        Inicia la grabación del clip.
        Escribe los frames del buffer (context_before) y sigue
        capturando context_after frames via add_frame().
        """
        with self._lock:
            if self._recording:
                logger.warning("Ya hay una grabación en curso — ignorando")
                return

            clip_path = os.path.join(
                self._clips_dir,
                f"{event.module_id}_{event.timestamp.strftime('%Y%m%d_%H%M%S')}.mp4"
            )

            # Determinar resolución desde el buffer
            if not self._buffer:
                logger.error("Buffer vacío — no se puede grabar clip")
                return

            h, w = self._buffer[0].shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self._writer = cv2.VideoWriter(clip_path, fourcc, self._fps, (w, h))

            if not self._writer.isOpened():
                logger.error(f"No se pudo crear VideoWriter: {clip_path}")
                return

            # Escribir frames del buffer (contexto antes)
            for frame in self._buffer:
                self._writer.write(frame)

            self._recording         = True
            self._frames_after      = 0
            self._on_ready          = on_ready
            self._current_clip_path = clip_path

            logger.info(
                f"Grabación iniciada: {clip_path} | "
                f"before={len(self._buffer)} frames"
            )

    def is_recording(self) -> bool:
        return self._recording

    def abort(self, reason: str) -> None:
        """
        Cierra la grabación en curso y descarta el buffer de contexto.
        Ver el puerto ClipRecorder para el razonamiento.
        """
        with self._lock:
            if self._recording:
                logger.warning(
                    f"Grabación cortada ({reason}) — clip parcial con "
                    f"{self._frames_after}/{self._context_after} frames posteriores"
                )
                self._finish_recording()   # entrega el clip via on_ready

            if self._buffer:
                logger.info(f"Buffer de contexto descartado ({reason}) — "
                            f"{len(self._buffer)} frames")
                self._buffer.clear()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _finish_recording(self) -> None:
        """Cierra el archivo y llama al callback. Debe llamarse con _lock."""
        if self._writer is not None:
            self._writer.release()
            self._writer = None

        clip_path       = self._current_clip_path
        on_ready        = self._on_ready
        self._recording = False
        self._frames_after      = 0
        self._on_ready          = None
        self._current_clip_path = None

        logger.info(f"Clip grabado: {clip_path}")

        if on_ready and clip_path:
            on_ready(clip_path)