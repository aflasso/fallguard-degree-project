"""
Puerto — cámara.
Define qué necesita la aplicación para capturar frames.
La implementación concreta está en infrastructure/video/opencv_camera.py
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional

import numpy as np


class Camera(ABC):

    @abstractmethod
    def read(self) -> Optional[np.ndarray]:
        """
        Lee el siguiente frame de la cámara.
        Retorna el frame BGR o None si no se pudo leer.
        """
        ...

    @property
    @abstractmethod
    def is_stream(self) -> bool:
        """
        True si la fuente es un stream de red (cámara IP/RTSP).
        En un stream, un None de read() es un corte temporal recuperable;
        en un archivo es el fin del video.
        """
        ...

    @abstractmethod
    def seconds_since_last_frame(self) -> float:
        """Segundos transcurridos desde el último frame leído con éxito."""
        ...

    @abstractmethod
    def reconnect(self, should_continue: Callable[[], bool]) -> bool:
        """
        Reabre un stream tras un corte, con reintentos hasta reconectar o
        hasta que should_continue() devuelva False.
        Retorna True si reconectó, False si se canceló o no es un stream.
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