"""
Puerto — escáner de cámaras.
Define qué necesita la aplicación para enumerar cámaras disponibles.
La implementación concreta está en infrastructure/video/opencv_camera_scanner.py
"""

from abc import ABC, abstractmethod
from typing import List

from domain.entities import CameraInfo


class CameraScanner(ABC):

    @abstractmethod
    def scan(self) -> List[CameraInfo]:
        """
        Escanea y retorna las cámaras físicas disponibles.

        Returns:
            Lista de CameraInfo con id y nombre de cada cámara encontrada
        """
        ...