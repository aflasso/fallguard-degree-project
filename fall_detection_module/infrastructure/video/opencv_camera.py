"""
Infraestructura — implementación de Camera usando OpenCV.
Implementa el puerto application/ports/camera.py
"""

import logging
from typing import Optional, Union

import cv2
import numpy as np

from application.ports.camera import Camera

logger = logging.getLogger(__name__)


class OpenCVCamera(Camera):
    """
    Implementa Camera usando cv2.VideoCapture.
    Encapsula el acceso a la cámara — Thread 1 depende del puerto
    Camera, no de OpenCV directamente.
    """
    
    def __init__(self, source: Union[int, str]):
        self._source = source
        self._cap    = cv2.VideoCapture(source)

        if not self._cap.isOpened():
            raise RuntimeError(f"No se pudo abrir fuente: {source}")

        logger.info(f"OpenCVCamera iniciada | source={source}")

    def read(self) -> Optional[np.ndarray]:
        ret, frame = self._cap.read()
        return frame if ret else None

    def release(self) -> None:
        self._cap.release()
        logger.info(f"OpenCVCamera liberada | id={self._camera_id}")

    def is_opened(self) -> bool:
        return self._cap.isOpened()