"""
Infraestructura — implementación de Camera usando OpenCV.
Implementa el puerto application/ports/camera.py
"""

import logging
import time
from typing import Callable, List, Optional, Union

import cv2
import numpy as np

from application.ports.camera import Camera

logger = logging.getLogger(__name__)

# Esquemas que indican un stream de red (cámara IP/RTSP) en vez de un archivo local.
_STREAM_SCHEMES = ("rtsp://", "rtmp://", "http://", "https://", "udp://", "tcp://")


class OpenCVCamera(Camera):
    """
    Implementa Camera usando cv2.VideoCapture.
    Encapsula el acceso a la cámara — Thread 1 depende del puerto
    Camera, no de OpenCV directamente.

    Distingue archivo/cámara local de stream de red: en un stream, un fallo
    de lectura es un corte temporal recuperable (se reconecta), no el fin.

    En streams se imponen timeouts de apertura y lectura al backend FFmpeg.
    Sin ellos una cámara IP congelada (celular en suspensión, Wi-Fi en ahorro
    de energía) deja el socket TCP abierto y read() bloquea para siempre: el
    módulo queda ciego sin devolver None y sin poder reconectar.
    """

    RECONNECT_MAX_BACKOFF = 10.0   # segundos máximo entre reintentos

    def __init__(
        self,
        source: Union[int, str],
        open_timeout_ms: int = 5000,
        read_timeout_ms: int = 5000,
    ):
        self._source = source
        self._open_timeout_ms = open_timeout_ms
        self._read_timeout_ms = read_timeout_ms
        self._is_stream = (
            isinstance(source, str) and source.lower().startswith(_STREAM_SCHEMES)
        )
        self._last_frame_ts = time.monotonic()
        self._cap = self._open()

        if not self._cap.isOpened():
            raise RuntimeError(f"No se pudo abrir fuente: {source}")

        logger.info(f"OpenCVCamera iniciada | source={source} | stream={self._is_stream}")

    def _open(self) -> cv2.VideoCapture:
        """
        Abre la fuente. Los timeouts solo aplican a streams: son propiedades del
        backend FFmpeg y una webcam local usa otro backend.
        """
        if not self._is_stream:
            return cv2.VideoCapture(self._source)

        params: List[int] = [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self._open_timeout_ms,
            cv2.CAP_PROP_READ_TIMEOUT_MSEC, self._read_timeout_ms,
        ]
        cap = cv2.VideoCapture(self._source, cv2.CAP_FFMPEG, params)
        if cap.isOpened():
            self._apply_stream_opts(cap)
        return cap

    def _apply_stream_opts(self, cap: cv2.VideoCapture) -> None:
        # Buffer mínimo: ante un hipo de red, descartar el atraso en vez de
        # acumular latencia. Algunos backends lo ignoran, por eso el try.
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

    @property
    def source(self) -> Union[int, str]:
        return self._source

    @property
    def is_stream(self) -> bool:
        return self._is_stream

    def seconds_since_last_frame(self) -> float:
        """Segundos transcurridos desde el último frame leído con éxito."""
        return time.monotonic() - self._last_frame_ts

    def read(self) -> Optional[np.ndarray]:
        ret, frame = self._cap.read()
        if not ret:
            return None
        self._last_frame_ts = time.monotonic()
        return frame

    def reconnect(self, should_continue: Callable[[], bool]) -> bool:
        """
        Reabre un stream tras un corte. Reintenta con backoff exponencial hasta
        reconectar o hasta que should_continue() devuelva False (cancelación).

        Retorna True si reconectó, False si se canceló o la fuente no es un stream
        (un archivo que devuelve None es fin de video, no un corte).
        """
        if not self._is_stream:
            return False

        self._cap.release()
        backoff = 1.0
        while should_continue():
            logger.info(f"Reintentando abrir stream: {self._source}")
            self._cap = self._open()
            if self._cap.isOpened():
                ret, _ = self._cap.read()   # frame de prueba
                if ret:
                    self._last_frame_ts = time.monotonic()
                    logger.info("Stream reconectado")
                    return True
                self._cap.release()

            # Espera con backoff, cooperativa con la cancelación.
            waited = 0.0
            while waited < backoff and should_continue():
                time.sleep(0.2)
                waited += 0.2
            backoff = min(backoff * 2, self.RECONNECT_MAX_BACKOFF)

        return False

    def release(self) -> None:
        self._cap.release()
        logger.info(f"OpenCVCamera liberada | source={self._source}")

    def is_opened(self) -> bool:
        return self._cap.isOpened()
