"""
Value Objects del dominio.
Objetos inmutables que representan conceptos del dominio con sus propias reglas de validación.
"""

from dataclasses import dataclass
from typing import Tuple
import numpy as np


@dataclass(frozen=True)
class FeatureSchema:
    """
    Describe el contrato de entrada de un modelo.
    Cada modelo declara el suyo — el dominio no asume nada fijo.

    Ejemplos:
        FeatureSchema(window_size=20, input_size=68, description="coco_xy_vel")
        FeatureSchema(window_size=20, input_size=69, description="coco_xy_vel_bbox")
    """
    window_size:  int
    input_size:   int
    description:  str

    def validate(self, frames: tuple) -> None:
        """
        Valida que una secuencia de frames cumpla el contrato del modelo.
        Lanza ValueError con mensaje claro si no cumple.
        """
        if len(frames) != self.window_size:
            raise ValueError(
                f"[{self.description}] Ventana incorrecta: "
                f"esperaba {self.window_size} frames, llegaron {len(frames)}"
            )
        for i, frame in enumerate(frames):
            if len(frame) != self.input_size:
                raise ValueError(
                    f"[{self.description}] Frame {i}: "
                    f"esperaba {self.input_size} features, llegaron {len(frame)}"
                )


# Constantes de Keypoints — fuera del dataclass para evitar conflicto
# con campos sin valor por defecto
COCO_INDICES: Tuple[int, ...] = tuple(range(17))
N_KEYPOINTS:  int             = 17
N_VALUES:     int             = 34   # x,y por cada punto


@dataclass(frozen=True)
class Keypoints:
    """
    Value Object que representa los keypoints de una persona en un frame.
    17 puntos COCO x (x, y) = 34 valores normalizados [0, 1].

    El orden de los indices COCO corresponde a la nomenclatura MediaPipe
    usada durante el entrenamiento:
        COCO 0  -> (nose)
        COCO 1  -> (left eye)
        COCO 2  -> (right eye)
        COCO 3  -> (left ear)
        COCO 4  -> (right ear)
        COCO 5  -> (left shoulder)
        COCO 6  -> (right shoulder)
        COCO 7  -> (left elbow)
        COCO 8  -> (right elbow)
        COCO 9  -> (left wrist)
        COCO 10 -> (right wrist)
        COCO 11 -> (left hip)
        COCO 12 -> (right hip)
        COCO 13 -> (left knee)
        COCO 14 -> (right knee)
        COCO 15 -> (left ankle)
        COCO 16 -> (right ankle)
    """

    values: tuple   # (34,) — inmutable

    def __post_init__(self):
        if len(self.values) != N_VALUES:
            raise ValueError(
                f"Keypoints invalidos: se esperaban {N_VALUES} valores "
                f"({N_KEYPOINTS} puntos x x,y), llegaron {len(self.values)}"
            )

    @classmethod
    def from_array(cls, arr: np.ndarray) -> "Keypoints":
        """Crea un Keypoints desde un numpy array (34,)."""
        return cls(values=tuple(arr.tolist()))

    def to_array(self) -> np.ndarray:
        """Convierte a numpy array (34,) para pasarlo al modelo."""
        return np.array(self.values, dtype=np.float32)


@dataclass(frozen=True)
class KeypointsSequence:
    """
    Value Object que representa una secuencia de frames para el LSTM.
    T frames de Keypoints — se valida contra el FeatureSchema del modelo activo.
    """
    frames: Tuple[Keypoints, ...]   # (T,) de Keypoints

    def validate_against(self, schema: FeatureSchema) -> None:
        """
        Valida la secuencia contra el contrato del modelo.
        Delega al FeatureSchema para que la validación esté centralizada.
        """
        raw_frames = tuple(kp.to_array() for kp in self.frames)
        schema.validate(raw_frames)

    def to_array(self) -> np.ndarray:
        """Convierte a numpy array (T, 34) para construir las features."""
        return np.stack([kp.to_array() for kp in self.frames])

    def __len__(self) -> int:
        return len(self.frames)