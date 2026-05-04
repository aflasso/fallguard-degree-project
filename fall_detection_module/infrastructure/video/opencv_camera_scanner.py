"""
Infraestructura — implementación de CameraScanner usando OpenCV.
Implementa el puerto application/ports/camera_scanner.py
"""

import logging
from typing import List

import cv2

from domain.entities import CameraInfo
from application.ports.camera_scanner import CameraScanner

logger = logging.getLogger(__name__)


class OpenCVCameraScanner(CameraScanner):
    """
    Implementa CameraScanner probando índices OpenCV del 0 al MAX.
    Confirma que cada cámara funciona leyendo un frame de prueba.
    """

    _MAX_CAMERAS_TO_SCAN = 5

    def scan(self) -> List[CameraInfo]:
        cameras = []

        for idx in range(self._MAX_CAMERAS_TO_SCAN):
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    name = "Camara integrada" if idx == 0 else f"Camara USB {idx}"
                    cameras.append(CameraInfo(id=idx, name=name))
                    logger.info(f"Camara encontrada: id={idx} name='{name}'")
                cap.release()

        logger.info(f"Camaras disponibles: {len(cameras)}")
        return cameras