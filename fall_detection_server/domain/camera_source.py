"""
Validación de la URL de cámara que el usuario configura desde la app.

El módulo local pasa esta cadena directo a `cv2.VideoCapture`. OpenCV abre
muchísimo más que streams de red: rutas del sistema de archivos, `file://`,
globs de imágenes. Sin allowlist, un `file:///etc/passwd` o `/app/models/...`
haría que el módulo intentara "detectar caídas" sobre un archivo local del
contenedor. Por eso el esquema se valida acá, en el dominio, y no en el schema
Pydantic: es una regla de negocio, no de transporte.
"""

from urllib.parse import urlparse

# Esquemas que OpenCV puede tratar como stream de red.
ALLOWED_SCHEMES = ("http", "https", "rtsp", "rtmp", "udp", "tcp")

MAX_URL_LENGTH = 500


def validate_camera_url(url: str) -> str:
    """
    Normaliza y valida la URL de la cámara.

    Returns:
        La URL sin espacios sobrantes.

    Raises:
        ValueError con un mensaje apto para mostrarle al usuario.
    """
    url = (url or "").strip()

    if not url:
        raise ValueError("La URL de la cámara no puede estar vacía")

    if len(url) > MAX_URL_LENGTH:
        raise ValueError(f"La URL supera los {MAX_URL_LENGTH} caracteres")

    try:
        parsed = urlparse(url)
    except ValueError as e:
        raise ValueError(f"URL inválida: {e}") from e

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        permitidos = ", ".join(ALLOWED_SCHEMES)
        raise ValueError(
            f"Esquema no permitido: '{parsed.scheme or '(ninguno)'}'. "
            f"Usar uno de: {permitidos}"
        )

    if not parsed.hostname:
        raise ValueError("La URL debe incluir un host (ej. http://192.168.1.42:8080/video)")

    # Credenciales embebidas (rtsp://usuario:clave@host). Todavía no se soportan:
    # quedarían en texto plano en Firestore, que el dueño del módulo puede leer.
    # Rechazarlas ahora significa que agregarlas después no requiere migrar datos.
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(
            "La URL no puede incluir usuario y contraseña. "
            "Usar una cámara sin autenticación."
        )

    return url
