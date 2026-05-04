"""
Servicio de dominio — reglas de negocio puras.
No depende de infraestructura ni de casos de uso.
"""

from collections import deque
from datetime import datetime, timezone
from typing import Optional

from domain.entities import FallPrediction, FallEvent


class FallDetectionService:
    """
    Encapsula la lógica de confirmación de caída:
      - Ventana deslizante de min_frames predicciones con label==1
      - Confianza media >= conf_lstm para confirmar el evento
      - Cooldown tras confirmar para no disparar alertas repetidas
    """

    def __init__(
        self,
        module_id:      str,
        min_frames:     int   = 3,
        conf_lstm:      float = 0.7,
        alert_cooldown: int   = 30,
    ):
        self.module_id      = module_id
        self.min_frames     = min_frames
        self.conf_lstm      = conf_lstm
        self.alert_cooldown = alert_cooldown

        # Ventana deslizante — solo guarda los últimos min_frames
        self._conf_window: deque = deque(maxlen=min_frames)

        # Estado interno
        self._alert_active:  bool = False
        self._silence_count: int  = 0

    def reset(self):
        """Limpia el estado — útil al cambiar de cámara o reiniciar."""
        self._conf_window.clear()
        self._alert_active  = False
        self._silence_count = 0

    def process(
        self,
        prediction: FallPrediction,
        frames_buffer: list,
    ) -> Optional[FallEvent]:
        """
        Procesa una predicción y retorna un FallEvent si se confirma caída,
        o None si no hay evento nuevo.

        Args:
            prediction:    resultado del LSTM para el frame actual
            frames_buffer: frames recientes del buffer circular (para el clip)

        Returns:
            FallEvent si se acaba de confirmar una caída, None en caso contrario
        """
        if prediction.is_fall:
            self._conf_window.append(prediction.prob_fall)
            self._silence_count = 0

            # Confirmar evento si la ventana está llena y supera el umbral
            if (
                not self._alert_active
                and len(self._conf_window) == self.min_frames
                and self._mean_conf() >= self.conf_lstm
            ):
                self._alert_active = True
                return FallEvent(
                    module_id=   self.module_id,
                    timestamp=   datetime.now(timezone.utc),
                    confidence=  round(self._mean_conf(), 4),
                    frame_count= self.min_frames,
                    frames=      list(frames_buffer),
                )

        else:
            if not self._alert_active:
                # Sin alerta activa: limpiar ventana
                self._conf_window.clear()
            else:
                # Alerta activa: contar silencio para desactivarla
                self._silence_count += 1
                if self._silence_count >= self.alert_cooldown:
                    self._alert_active  = False
                    self._silence_count = 0
                    self._conf_window.clear()

        return None

    # ── Helpers ───────────────────────────────────────────────────────────

    def _mean_conf(self) -> float:
        if not self._conf_window:
            return 0.0
        return sum(self._conf_window) / len(self._conf_window)

    @property
    def alert_active(self) -> bool:
        return self._alert_active

    @property
    def current_conf(self) -> float:
        """Confianza media actual de la ventana deslizante."""
        return round(self._mean_conf(), 4)