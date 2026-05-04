"""
Caso de uso: DetectFall
Orquesta la extracción de keypoints, la construcción de la secuencia
y la predicción del modelo. Delega la lógica de confirmación al FallDetectionService.
"""

from collections import deque
from typing import Optional
import numpy as np

from domain.entities import FallEvent
from domain.value_objects import Keypoints, KeypointsSequence
from domain.fall_service import FallDetectionService
from application.ports.keypoint_extractor import KeypointExtractor
from application.ports.fall_predictor import FallPredictor


class DetectFall:
    """
    Caso de uso principal del módulo.

    Por cada frame:
      1. Extrae keypoints con YOLO-pose
      2. Acumula en buffer deslizante
      3. Construye KeypointsSequence y valida contra el schema del modelo
      4. Predice con el LSTM
      5. Pasa la predicción al FallDetectionService
      6. Retorna FallEvent si se confirma caída, None si no

    También mantiene un buffer de frames BGR para el clip de video.
    """

    def __init__(
        self,
        extractor:  KeypointExtractor,
        predictor:  FallPredictor,
        fall_service: FallDetectionService,
    ):
        self._extractor    = extractor
        self._predictor    = predictor
        self._fall_service = fall_service

        window = predictor.schema.window_size

        # Buffer deslizante de keypoints para el LSTM
        self._kp_buffer: deque = deque(maxlen=window)

        # Buffer deslizante de frames BGR para el clip de video
        # Guarda más frames que la ventana para tener contexto antes de la caída
        self._frame_buffer: deque = deque(maxlen=window * 3)

        # Contador de frames sin detección de persona
        self._missing_frames: int = 0
        self._MAX_MISSING:    int = 10

    def execute(self, frame: np.ndarray) -> Optional[FallEvent]:
        """
        Procesa un frame y retorna un FallEvent si se confirma caída.

        Args:
            frame: frame BGR capturado desde la cámara

        Returns:
            FallEvent si se acaba de confirmar una caída, None en caso contrario
        """
        # Siempre guardar el frame en el buffer de video
        self._frame_buffer.append(frame.copy())

        # Extraer keypoints
        keypoints: Optional[Keypoints] = self._extractor.extract(frame)

        if keypoints is not None:
            self._missing_frames = 0
            self._kp_buffer.append(keypoints)

            # Solo predecir cuando el buffer está completo
            if len(self._kp_buffer) == self._predictor.schema.window_size:
                sequence = KeypointsSequence(frames=tuple(self._kp_buffer))

                prediction = self._predictor.predict(sequence)

                return self._fall_service.process(
                    prediction=prediction,
                    frames_buffer=list(self._frame_buffer),
                )
        else:
            self._missing_frames += 1
            if self._missing_frames > self._MAX_MISSING:
                # Persona ausente demasiado tiempo — resetear estado
                self._kp_buffer.clear()
                self._fall_service.reset()
                self._missing_frames = 0

        return None

    def reset(self):
        """Limpia el estado — útil al cambiar de cámara."""
        self._kp_buffer.clear()
        self._frame_buffer.clear()
        self._fall_service.reset()
        self._missing_frames = 0

    @property
    def alert_active(self) -> bool:
        """True si hay una alerta activa en el servicio de dominio."""
        return self._fall_service.alert_active

    @property
    def current_conf(self) -> float:
        """Confianza media actual de la ventana deslizante."""
        return self._fall_service.current_conf