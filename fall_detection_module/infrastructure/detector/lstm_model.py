"""
Infraestructura — implementación del FallPredictor usando PyTorch LSTM.
Implementa el puerto application/ports/fall_predictor.py
"""

import logging
import numpy as np
import torch
import torch.nn as nn
from pathlib import Path

from domain.entities import FallPrediction
from domain.value_objects import FeatureSchema, KeypointsSequence
from application.ports.fall_predictor import FallPredictor

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Arquitectura del modelo — debe coincidir exactamente con la usada al entrenar
# ──────────────────────────────────────────────────────────────────────────────
class _FallLSTM(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, num_classes, dropout):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        self.dropout = nn.Dropout(dropout)
        self.fc      = nn.Linear(hidden_size, num_classes)

    def forward(self, x):
        out, _ = self.lstm(x)
        out    = out[:, -1, :]
        out    = self.dropout(out)
        return self.fc(out)


# ──────────────────────────────────────────────────────────────────────────────
# Implementación del puerto FallPredictor
# ──────────────────────────────────────────────────────────────────────────────
class LSTMFallPredictor(FallPredictor):
    """
    Implementa FallPredictor usando el modelo LSTM entrenado.

    Recibe una KeypointsSequence con keypoints crudos (T, 34) y construye
    internamente las features completas (T, 68) agregando velocidad.
    La validación del contrato ocurre después de construir las features.
    """

    def __init__(self, model_path: str, device: str = "cuda:0"):
        self._device = torch.device(
            device if torch.cuda.is_available() else "cpu"
        )
        self._schema, self._model = self._load(model_path)
        logger.info(
            f"LSTMFallPredictor cargado | "
            f"ventana={self._schema.window_size} | "
            f"features={self._schema.input_size} | "
            f"device={self._device}"
        )

    # ── Puerto ────────────────────────────────────────────────────────────

    @property
    def schema(self) -> FeatureSchema:
        return self._schema

    def predict(self, sequence: KeypointsSequence) -> FallPrediction:
        """
        1. Construye features internamente: x,y (34) + velocidad x,y (34) = 68
        2. Valida contra el schema
        3. Pasa al modelo y retorna predicción
        """
        # Construir features internamente
        features = self._build_features(sequence)

        # Validar contra el contrato del modelo
        self._schema.validate(tuple(features))

        # Inferencia
        X = torch.tensor(features, dtype=torch.float32) \
                 .unsqueeze(0) \
                 .to(self._device)   # (1, T, 68)

        with torch.no_grad():
            logits = self._model(X)
            probs  = torch.softmax(logits, dim=1)[0].cpu().numpy()

        return FallPrediction(
            label=       int(np.argmax(probs)),
            prob_normal= float(probs[0]),
            prob_fall=   float(probs[1]),
            prob_post=   float(probs[2]),
        )

    # ── Helpers ───────────────────────────────────────────────────────────

    def _build_features(self, sequence: KeypointsSequence) -> np.ndarray:
        """
        Construye el array de features completo.
        coco_xy_vel: x,y (34) + velocidad x,y (34) = 68 features/frame
        La velocidad es un detalle de implementación de este modelo.
        """
        arr = sequence.to_array()       # (T, 34)
        vel = np.zeros_like(arr)
        vel[1:] = arr[1:] - arr[:-1]
        return np.concatenate([arr, vel], axis=1)   # (T, 68)

    def _load(self, model_path: str):
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"Modelo no encontrado: {model_path}")

        checkpoint = torch.load(model_path, map_location="cpu")
        hp         = checkpoint["hyperparams"]

        schema = FeatureSchema(
            window_size= hp["window"],
            input_size=  hp["input_size"],
            description= hp.get("feature_mode", "coco_xy_vel"),
        )

        model = _FallLSTM(
            input_size=  hp["input_size"],
            hidden_size= hp["hidden_size"],
            num_layers=  hp["num_layers"],
            num_classes= hp["num_classes"],
            dropout=     hp["dropout"],
        ).to(self._device)

        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()

        return schema, model