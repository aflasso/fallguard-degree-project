"""
Puerto — cámara.
Define qué necesita la aplicación para capturar frames.
La implementación concreta está en infrastructure/video/opencv_camera.py
"""

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np


class Camera(ABC):

    @abstractmethod
    def read(self) -> Optional[np.ndarray]:
        """
        Lee el siguiente frame de la cámara.
        Retorna el frame BGR o None si no se pudo leer.
        """
        ...

    @abstractmethod
    def release(self) -> None:
        """Libera los recursos de la cámara."""
        ...

    @abstractmethod
    def is_opened(self) -> bool:
        """True si la cámara está abierta y lista."""
        ...