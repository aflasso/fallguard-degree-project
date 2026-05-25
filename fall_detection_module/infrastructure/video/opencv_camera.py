"""
Infraestructura — implementación de Camera usando OpenCV.
Implementa el puerto application/ports/camera.py
"""

import logging
import time
from typing import Callable, Optional, Union

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
    """

    RECONNECT_MAX_BACKOFF = 10.0   # segundos máximo entre reintentos

    def __init__(self, source: Union[int, str]):
        self._source = source
        self._is_stream = (
            isinstance(source, str) and source.lower().startswith(_STREAM_SCHEMES)
        )
        self._cap = cv2.VideoCapture(source)

        if not self._cap.isOpened():
            raise RuntimeError(f"No se pudo abrir fuente: {source}")

        if self._is_stream:
            self._apply_stream_opts()

        logger.info(f"OpenCVCamera iniciada | source={source} | stream={self._is_stream}")

    def _apply_stream_opts(self) -> None:
        # Buffer mínimo: ante un hipo de red, descartar el atraso en vez de
        # acumular latencia. Algunos backends lo ignoran, por eso el try.
        try:
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

    @property
    def is_stream(self) -> bool:
        return self._is_stream

    def read(self) -> Optional[np.ndarray]:
        ret, frame = self._cap.read()
        return frame if ret else None

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
            self._cap = cv2.VideoCapture(self._source)
            if self._cap.isOpened():
                self._apply_stream_opts()
                ret, _ = self._cap.read()   # frame de prueba
                if ret:
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
