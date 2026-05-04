"""
Infraestructura — implementación del KeypointExtractor usando YOLO-pose.
Implementa el puerto application/ports/keypoint_extractor.py
"""

import logging
from typing import Optional

import numpy as np
from ultralytics import YOLO

from domain.value_objects import Keypoints, COCO_INDICES
from application.ports.keypoint_extractor import KeypointExtractor

logger = logging.getLogger(__name__)

# Mapeo COCO (índice YOLO-pose) → índice en el array de keypoints
# El orden debe coincidir exactamente con el usado durante el entrenamiento
KEYPOINT_MAP = [
    (0, "nose"), (1, "left_eye"), (2, "right_eye"), (3, "left_ear"), (4, "right_ear"),
    (5, "left_shoulder"), (6, "right_shoulder"), (7, "left_elbow"), (8, "right_elbow"),
    (9, "left_wrist"), (10, "right_wrist"), (11, "left_hip"), (12, "right_hip"),
    (13, "left_knee"), (14, "right_knee"), (15, "left_ankle"), (16, "right_ankle")
]


class YoloPoseExtractor(KeypointExtractor):
    """
    Implementa KeypointExtractor usando YOLO11x-pose.

    Detecta la persona con mayor confianza en el frame y extrae
    sus 17 keypoints COCO normalizados [0,1] como un Keypoints Value Object.
    """

    def __init__(self, model_path: str, conf: float = 0.8, device: str = "cuda:0"):
        self._conf   = conf
        self._device = device
        self._model  = YOLO(model_path)
        logger.info(
            f"YoloPoseExtractor cargado | "
            f"conf={conf} | device={device}"
        )

    def extract(self, frame: np.ndarray) -> Optional[Keypoints]:
        """
        Dado un frame BGR retorna un Keypoints con x,y normalizados
        de los 17 keypoints COCO, o None si no se detecta persona.
        """
        results  = self._model(
            frame,
            conf=    self._conf,
            device=  self._device,
            verbose= False,
        )

        boxes    = results[0].boxes
        kps_data = results[0].keypoints

        if boxes is None or len(boxes) == 0:
            return None
        if kps_data is None or len(kps_data.xyn) == 0:
            return None

        # Tomar la persona con mayor confianza
        best_idx = int(boxes.conf.argmax())
        xyn      = kps_data.xyn[best_idx].cpu().numpy()   # (17, 2) normalizado

        # Construir array plano (34,): x0, y0, x1, y1, ...
        values = np.zeros(len(KEYPOINT_MAP) * 2, dtype=np.float32)
        for map_idx, (coco_idx, _) in enumerate(KEYPOINT_MAP):
            values[map_idx * 2]     = xyn[coco_idx, 0]   # x normalizado
            values[map_idx * 2 + 1] = xyn[coco_idx, 1]   # y normalizado

        return Keypoints.from_array(values)