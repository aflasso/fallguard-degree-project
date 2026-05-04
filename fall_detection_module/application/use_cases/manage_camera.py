"""
Caso de uso: ManageCamera
Gestiona la selección y cambio de cámara del módulo.
  1. Lista las cámaras físicas disponibles via CameraScanner
  2. Activa la cámara seleccionada por el usuario desde la app
"""

import logging
from typing import List, Optional

from domain.entities import CameraInfo
from application.ports.camera_scanner import CameraScanner

logger = logging.getLogger(__name__)


class ManageCamera:
    """
    Caso de uso para gestión de cámara.
    No depende de OpenCV ni de ninguna infraestructura concreta —
    recibe un CameraScanner por inyección.
    """

    def __init__(self, scanner: CameraScanner):
        self._scanner               = scanner
        self._active_camera_id:     Optional[int]       = None
        self._available_cameras:    List[CameraInfo]    = []

    def scan_cameras(self) -> List[CameraInfo]:
        """
        Escanea y retorna las cámaras físicas disponibles.
        Delega al CameraScanner de infraestructura.
        """
        self._available_cameras = self._scanner.scan()
        return list(self._available_cameras)

    def set_camera(self, camera_id: int) -> CameraInfo:
        """
        Establece la cámara activa.

        Raises:
            ValueError si camera_id no está en la lista de cámaras disponibles
        """
        available_ids = [c.id for c in self._available_cameras]

        if camera_id not in available_ids:
            raise ValueError(
                f"Camara {camera_id} no disponible. "
                f"Disponibles: {available_ids}"
            )

        self._active_camera_id = camera_id
        camera = next(c for c in self._available_cameras if c.id == camera_id)
        logger.info(f"Camara activa: id={camera_id} name='{camera.name}'")
        return camera

    def get_active_camera(self) -> Optional[CameraInfo]:
        """Retorna la cámara activa o None si no hay ninguna seleccionada."""
        if self._active_camera_id is None:
            return None
        return next(
            (c for c in self._available_cameras if c.id == self._active_camera_id),
            None,
        )

    def get_available_cameras(self) -> List[CameraInfo]:
        """Retorna la lista de cámaras disponibles del último escaneo."""
        return list(self._available_cameras)

    @property
    def has_active_camera(self) -> bool:
        """True si hay una cámara activa seleccionada."""
        return self._active_camera_id is not None