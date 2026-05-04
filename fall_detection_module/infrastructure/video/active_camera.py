"""
Utilidad — contenedor thread-safe para la cámara activa.
Permite cambiar la cámara desde cualquier thread sin nonlocal ni condiciones de carrera.
"""

import logging
import threading

from infrastructure.video.opencv_camera import OpenCVCamera

logger = logging.getLogger(__name__)


class ActiveCamera:
    """
    Contenedor thread-safe para la cámara activa.
    Thread 1 lee frames continuamente via instance.read().
    Cuando el servidor manda set_camera, switch() cambia la instancia
    de forma segura sin que Thread 1 note la diferencia.
    """

    def __init__(self, camera: OpenCVCamera):
        self._instance = camera
        self._lock     = threading.Lock()

    @property
    def instance(self) -> OpenCVCamera:
        with self._lock:
            return self._instance

    def switch(self, camera_id: int) -> None:
        """
        Libera la cámara actual y abre la nueva.
        Thread-safe — Thread 1 terminará el frame actual antes de
        leer la nueva instancia.
        """
        with self._lock:
            logger.info(f"Cambiando cámara → id={camera_id}")
            self._instance.release()
            self._instance = OpenCVCamera(camera_id)
            logger.info(f"Cámara activa: id={camera_id}")