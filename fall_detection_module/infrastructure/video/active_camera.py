"""
Utilidad — contenedor de la cámara activa con cambio de fuente en caliente.

**Por qué Thread 3 no abre ni cierra la cámara.**
`cv2.VideoCapture` no es thread-safe. Si Thread 3 (WebSocket) llamara a
`release()` sobre la cámara vieja mientras Thread 1 está bloqueado dentro de
`read()` en ese mismo objeto, el resultado es un segfault intermitente.

Por eso el cambio de fuente es en dos tiempos:
  - Thread 3 llama a `request_source(...)` — solo guarda la fuente deseada.
  - Thread 1 llama a `needs_open()` / `open()` al tope de su loop, cuando sabe
    que no hay ningún `read()` en vuelo.

`open()` es también el camino de reintento: si la fuente no abre, `instance`
queda en None y Thread 1 vuelve a intentar con backoff.
"""

import logging
import threading
from typing import Optional, Union

from infrastructure.video.opencv_camera import OpenCVCamera

logger = logging.getLogger(__name__)

Source = Union[int, str]


class ActiveCamera:
    """
    Contenedor de la cámara activa. Puede estar vacío: un módulo recién
    instalado arranca sin fuente y espera a que la app le configure una.
    """

    def __init__(
        self,
        source:          Optional[Source] = None,
        open_timeout_ms: int = 5000,
        read_timeout_ms: int = 5000,
    ):
        self._instance:       Optional[OpenCVCamera] = None
        self._desired_source: Optional[Source]       = source
        self._open_timeout_ms = open_timeout_ms
        self._read_timeout_ms = read_timeout_ms
        self._lock = threading.Lock()

    # ── Lectura (Thread 1) ────────────────────────────────────────────────

    @property
    def instance(self) -> Optional[OpenCVCamera]:
        with self._lock:
            return self._instance

    @property
    def source(self) -> Optional[Source]:
        with self._lock:
            return self._desired_source

    def has_source(self) -> bool:
        return self.source is not None

    def needs_open(self) -> bool:
        """
        True si hay una fuente deseada sin abrir: nunca se abrió, falló el
        intento anterior, o Thread 3 pidió otra distinta.
        """
        with self._lock:
            if self._desired_source is None:
                return False
            if self._instance is None:
                return True
            return self._instance.source != self._desired_source

    # ── Cambio de fuente (Thread 3) ───────────────────────────────────────

    def request_source(self, source: Source) -> None:
        """
        Solicita el cambio de fuente. NO abre ni cierra nada — de eso se encarga
        Thread 1 en `open()`. Ver el docstring del módulo.
        """
        with self._lock:
            if self._desired_source == source:
                logger.info(f"Fuente sin cambios: {source}")
                return
            self._desired_source = source
        logger.info(f"Cambio de fuente solicitado: {source}")

    # ── Apertura (Thread 1, exclusivo) ────────────────────────────────────

    def open(self) -> bool:
        """
        Cierra la cámara actual y abre la fuente deseada.
        **Solo puede llamarse desde Thread 1**, con ningún `read()` en vuelo.

        Retorna True si quedó abierta, False si falló (el llamador reintenta).
        """
        with self._lock:
            source = self._desired_source
            old    = self._instance
            self._instance = None

        if old is not None:
            old.release()

        if source is None:
            return False

        try:
            camera = OpenCVCamera(
                source,
                open_timeout_ms=self._open_timeout_ms,
                read_timeout_ms=self._read_timeout_ms,
            )
        except RuntimeError as e:
            logger.error(f"No se pudo abrir la fuente: {e}")
            return False

        with self._lock:
            # Thread 3 pudo pedir otra fuente mientras abríamos ésta.
            if self._desired_source != source:
                logger.info("La fuente cambió durante la apertura — descartando")
                camera.release()
                return False
            self._instance = camera

        logger.info(f"Cámara activa: {source} | stream={camera.is_stream}")
        return True

    def release(self) -> None:
        with self._lock:
            camera = self._instance
            self._instance = None
        if camera is not None:
            camera.release()
