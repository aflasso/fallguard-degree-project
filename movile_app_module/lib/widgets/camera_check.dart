/// Estado de la comprobación de una cámara antes de guardarla.
enum CameraCheck {
  /// El campo está vacío. La cámara es opcional al vincular.
  empty,

  /// Hay una URL que nunca se probó, o que se editó después de probarla.
  unchecked,

  /// Conectando; todavía no llegó ningún frame.
  checking,

  /// Llegó imagen: la URL está verificada.
  live,

  /// Se probó y falló.
  failed,

  /// El esquema no admite vista previa (rtsp://). No se puede verificar.
  unsupported,
}

/// Qué hacer con el botón de confirmación según el estado de la comprobación.
class CameraSaveDecision {
  const CameraSaveDecision({required this.enabled, required this.unverified});

  /// Si el botón está habilitado.
  final bool enabled;

  /// Si se guardaría sin haber visto la cámara. El botón debe decirlo.
  final bool unverified;
}

/// Regla de guardado: el camino normal exige haber visto un frame.
///
/// El escape existe y es explícito para dos casos legítimos en los que la
/// previsualización no puede funcionar aunque la URL sea correcta:
///   - RTSP, que no se puede reproducir sin una dependencia nativa.
///   - El celular fuera de la LAN de la cámara (ej. en datos móviles), mientras
///     el módulo sí la alcanza desde la Wi-Fi del hogar.
///
/// `unchecked` y `checking` bloquean: hay una URL sin verificar y todavía se
/// puede verificar, así que no hay razón para saltearse la comprobación.
CameraSaveDecision cameraSaveDecision(
  CameraCheck check, {
  required bool cameraOptional,
}) {
  switch (check) {
    case CameraCheck.empty:
      return CameraSaveDecision(enabled: cameraOptional, unverified: false);
    case CameraCheck.live:
      return const CameraSaveDecision(enabled: true, unverified: false);
    case CameraCheck.failed:
    case CameraCheck.unsupported:
      return const CameraSaveDecision(enabled: true, unverified: true);
    case CameraCheck.unchecked:
    case CameraCheck.checking:
      return const CameraSaveDecision(enabled: false, unverified: false);
  }
}
