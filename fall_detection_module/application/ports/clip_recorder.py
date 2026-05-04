"""
Puerto — grabador de clips de video.
Define qué necesita la aplicación para grabar un clip con contexto.
La implementación concreta está en infrastructure/video/clip_recorder.py
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional

import numpy as np

from domain.entities import FallEvent


class ClipRecorder(ABC):

    @abstractmethod
    def add_frame(self, frame: np.ndarray) -> None:
        """
        Agrega un frame al buffer circular.
        Se llama por cada frame capturado, independientemente de si hay caída.
        """
        ...

    @abstractmethod
    def record(
        self,
        event: FallEvent,
        on_ready: Callable[[str], None],
    ) -> None:
        """
        Inicia la grabación de un clip para el evento de caída dado.
        Toma context_before frames del buffer ya acumulado y sigue
        capturando context_after frames adicionales antes de cerrar el clip.

        Args:
            event:    FallEvent confirmado por el dominio
            on_ready: callback que se llama con la ruta del clip cuando está listo
                      on_ready(clip_path: str)
        """
        ...

    @abstractmethod
    def is_recording(self) -> bool:
        """True si hay una grabación en curso."""
        ...