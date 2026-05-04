"""
Puerto — predictor de caídas.
Define qué necesita la aplicación para predecir si una secuencia es una caída.
La implementación concreta (LSTM) está en infrastructure/detector/lstm_model.py
"""

from abc import ABC, abstractmethod

from domain.entities import FallPrediction
from domain.value_objects import KeypointsSequence, FeatureSchema


class FallPredictor(ABC):

    @property
    @abstractmethod
    def schema(self) -> FeatureSchema:
        """
        Retorna el FeatureSchema del modelo — ventana, features, descripción.
        Se usa para validar la secuencia antes de inferencia.
        """
        ...

    @abstractmethod
    def predict(self, sequence: KeypointsSequence) -> FallPrediction:
        """
        Dado una KeypointsSequence validada retorna la predicción del modelo.

        Args:
            sequence: secuencia de T frames de Keypoints

        Returns:
            FallPrediction con label y probabilidades
        """
        ...