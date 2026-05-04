"""
Puerto — extractor de keypoints.
Define qué necesita la aplicación para extraer keypoints de un frame.
La implementación concreta (YOLO-pose) está en infrastructure/detector/yolo_pose.py
"""

from abc import ABC, abstractmethod
from typing import Optional
import numpy as np

from domain.value_objects import Keypoints


class KeypointExtractor(ABC):

    @abstractmethod
    def extract(self, frame: np.ndarray) -> Optional[Keypoints]:
        """
        Dado un frame BGR retorna un Keypoints con x,y normalizados
        de los 17 keypoints COCO, o None si no se detecta persona.
        """
        ...