import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../theme/app_theme.dart';
import '../services/alert_service.dart';
import '../widgets/mjpeg_view.dart';
import '../widgets/camera_check.dart';

/// Campo de URL de cámara con vista previa bajo demanda.
///
/// La previsualización es una comprobación *del celular*, no del módulo: los dos
/// pueden ver la red de forma distinta. La confirmación autoritativa llega
/// después, cuando el módulo reporta `camera_ok` por WebSocket.
///
/// Informa su estado al diálogo que lo contiene, que lo usa para habilitar o no
/// el botón de guardar. Si la URL se edita después de una previsualización
/// exitosa, el estado vuelve a `unchecked`: lo que se guarda tiene que ser lo
/// que se vio.
class _CameraUrlEditor extends StatefulWidget {
  const _CameraUrlEditor({required this.controller, required this.onCheck});

  final TextEditingController controller;
  final ValueChanged<CameraCheck> onCheck;

  @override
  State<_CameraUrlEditor> createState() => _CameraUrlEditorState();
}

class _CameraUrlEditorState extends State<_CameraUrlEditor> {
  String? _previewUrl;
  CameraCheck _check = CameraCheck.empty;

  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onTextChanged);
    _check = widget.controller.text.trim().isEmpty
        ? CameraCheck.empty
        : CameraCheck.unchecked;
    // Al editar una cámara ya configurada el campo arranca lleno pero sin
    // verificar. El diálogo tiene que enterarse, o creería que está vacío.
    // Se difiere: no se puede llamar setState del padre durante su build.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) widget.onCheck(_check);
    });
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onTextChanged);
    super.dispose();
  }

  void _setCheck(CameraCheck value) {
    if (_check == value) return;
    setState(() => _check = value);
    widget.onCheck(value);
  }

  void _onTextChanged() {
    final url = widget.controller.text.trim();

    // La URL cambió respecto de la que se previsualizó: lo verificado ya no
    // corresponde a lo que se guardaría.
    if (_previewUrl != null && url != _previewUrl) {
      setState(() => _previewUrl = null);
    }
    _setCheck(url.isEmpty ? CameraCheck.empty : CameraCheck.unchecked);
  }

  void _preview() {
    final url = widget.controller.text.trim();
    if (url.isEmpty) return;

    setState(() => _previewUrl = url);
    _setCheck(MjpegView.canPreview(url) ? CameraCheck.checking : CameraCheck.unsupported);
  }

  @override
  Widget build(BuildContext context) {
    final url = _previewUrl;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextField(
          controller: widget.controller,
          keyboardType: TextInputType.url,
          autocorrect: false,
          decoration: const InputDecoration(
            labelText: 'URL de la cámara',
            hintText: 'http://192.168.1.42:8080/video',
          ),
          onSubmitted: (_) => _preview(),
        ),
        const SizedBox(height: 8),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            onPressed: _check == CameraCheck.empty ? null : _preview,
            icon: const Icon(Icons.play_circle_outline, size: 18),
            label: Text(_check == CameraCheck.live ? 'Reintentar' : 'Probar cámara'),
          ),
        ),
        if (url != null) ...[
          const SizedBox(height: 4),
          if (MjpegView.canPreview(url))
            // La key fuerza a reconstruir el widget (y reconectar) al cambiar la URL.
            MjpegView(
              key: ValueKey(url),
              url: url,
              onLive: () => _setCheck(CameraCheck.live),
              // Haber visto la cámara es un hecho consumado: un corte posterior
              // no lo revierte. Solo editar la URL invalida la verificación.
              onFailed: (_) {
                if (_check != CameraCheck.live) _setCheck(CameraCheck.failed);
              },
            )
          else
            _notice('Sin vista previa para esta URL. Si la guardas, el módulo '
                'confirmará si puede ver la cámara.'),
        ],
        if (_check == CameraCheck.unchecked) ...[
          const SizedBox(height: 8),
          _notice('Prueba la cámara para ver qué está capturando antes de guardar.'),
        ],
      ],
    );
  }

  Widget _notice(String text) => Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppTheme.warningLight,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(
          text,
          style: GoogleFonts.manrope(fontSize: 12, color: AppTheme.textSecondary),
        ),
      );
}

class LinkedCamerasScreen extends StatefulWidget {
  const LinkedCamerasScreen({super.key});

  @override
  State<LinkedCamerasScreen> createState() => _LinkedCamerasScreenState();
}

/// Ancho de los diálogos que contienen la vista previa. `AlertDialog` mide su
/// contenido con `IntrinsicWidth`, y un stream de video no tiene ancho natural:
/// sin esto el layout falla con `'input.isFinite': is not true`.
const double _dialogWidth = 300;

/// Botón de confirmación gobernado por [cameraSaveDecision].
Widget _confirmButton({
  required CameraCheck check,
  required bool cameraOptional,
  required String label,
  required VoidCallback onConfirm,
  bool otherFieldsValid = true,
}) {
  final decision = cameraSaveDecision(check, cameraOptional: cameraOptional);

  return TextButton(
    onPressed:
        (decision.enabled && otherFieldsValid) ? onConfirm : null,
    child: Text(decision.unverified ? '$label sin verificar' : label),
  );
}

/// Diálogo de vinculación. La cámara es opcional acá: se puede vincular primero
/// y configurarla después desde la lista.
class _LinkModuleDialog extends StatefulWidget {
  const _LinkModuleDialog();

  @override
  State<_LinkModuleDialog> createState() => _LinkModuleDialogState();
}

class _LinkModuleDialogState extends State<_LinkModuleDialog> {
  final _idController = TextEditingController();
  final _nameController = TextEditingController();
  final _urlController = TextEditingController();
  CameraCheck _check = CameraCheck.empty;

  @override
  void initState() {
    super.initState();
    _idController.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _idController.dispose();
    _nameController.dispose();
    _urlController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(
        'Vincular nuevo módulo',
        style: GoogleFonts.manrope(fontWeight: FontWeight.w700),
      ),
      // Ancho fijo: AlertDialog mide su contenido con IntrinsicWidth, y la vista
      // previa no tiene un ancho natural que ofrecerle.
      content: SizedBox(
        width: _dialogWidth,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: _idController,
                autofocus: true,
                decoration: const InputDecoration(
                  labelText: 'ID del módulo',
                  hintText: 'FG-XXXX-XXXX',
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _nameController,
                decoration: const InputDecoration(
                  labelText: 'Nombre visible (opcional)',
                  hintText: 'Ej: Sala principal',
                ),
              ),
              const SizedBox(height: 12),
              _CameraUrlEditor(
                controller: _urlController,
                onCheck: (c) => setState(() => _check = c),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancelar'),
        ),
        _confirmButton(
          check: _check,
          cameraOptional: true,
          label: 'Vincular',
          otherFieldsValid: _idController.text.trim().isNotEmpty,
          onConfirm: () => Navigator.pop(context, (
            _idController.text.trim(),
            _nameController.text.trim(),
            _urlController.text.trim(),
          )),
        ),
      ],
    );
  }
}

/// Diálogo de configuración de cámara. Acá la URL es obligatoria.
class _CameraSourceDialog extends StatefulWidget {
  const _CameraSourceDialog({this.currentUrl});

  final String? currentUrl;

  @override
  State<_CameraSourceDialog> createState() => _CameraSourceDialogState();
}

class _CameraSourceDialogState extends State<_CameraSourceDialog> {
  late final TextEditingController _controller =
      TextEditingController(text: widget.currentUrl ?? '');
  CameraCheck _check = CameraCheck.empty;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(
        'Cámara del módulo',
        style: GoogleFonts.manrope(fontWeight: FontWeight.w700),
      ),
      content: SizedBox(
        width: _dialogWidth,
        child: SingleChildScrollView(
          child: _CameraUrlEditor(
            controller: _controller,
            onCheck: (c) => setState(() => _check = c),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancelar'),
        ),
        _confirmButton(
          check: _check,
          cameraOptional: false,   // sin cámara el módulo no detecta nada
          label: 'Guardar',
          onConfirm: () => Navigator.pop(context, _controller.text.trim()),
        ),
      ],
    );
  }
}

class _LinkedCamerasScreenState extends State<LinkedCamerasScreen> {
  void _snack(String message, {bool error = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(message),
      backgroundColor: error ? AppTheme.alertRed : null,
    ));
  }

  Future<void> _showLinkDialog() async {
    final result = await showDialog<(String, String, String)>(
      context: context,
      builder: (_) => const _LinkModuleDialog(),
    );
    if (result == null || !mounted) return;
    final (moduleId, displayName, cameraUrl) = result;

    try {
      await AlertService.linkModule(moduleId);
    } catch (_) {
      _snack('No se pudo vincular el módulo. Verifica el ID.', error: true);
      return;
    }

    // Vinculado. El nombre y la cámara son opcionales: si alguno falla, el
    // módulo ya quedó vinculado y se avisa para editarlo desde la lista.
    if (displayName.isNotEmpty) {
      try {
        await AlertService.renameModule(moduleId, displayName);
      } catch (_) {
        _snack('Módulo vinculado, pero no se pudo guardar el nombre. '
            'Edítalo luego.', error: true);
        return;
      }
    }

    if (cameraUrl.isNotEmpty) {
      try {
        await AlertService.setModuleCamera(moduleId, cameraUrl);
      } catch (e) {
        _snack('Módulo vinculado, pero la cámara no se guardó: '
            '${_message(e)}', error: true);
        return;
      }
    }

    _snack('Módulo vinculado correctamente');
  }

  /// Mensaje legible de una Exception lanzada por AlertService.
  static String _message(Object e) =>
      e.toString().replaceFirst('Exception: ', '');

  Future<void> _changeCamera(String moduleId, String? currentUrl) async {
    final url = await showDialog<String>(
      context: context,
      builder: (_) => _CameraSourceDialog(currentUrl: currentUrl),
    );
    if (url == null || url.isEmpty || !mounted) return;

    try {
      await AlertService.setModuleCamera(moduleId, url);
      _snack('Cámara actualizada. El módulo confirmará si puede verla.');
    } catch (e) {
      _snack(_message(e), error: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: AppTheme.background,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: AppTheme.textPrimary),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(
          'Cámaras Vinculadas',
          style: GoogleFonts.manrope(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: AppTheme.textPrimary,
          ),
        ),
        centerTitle: true,
      ),
      body: StreamBuilder<List<Map<String, dynamic>>>(
        stream: AlertService.linkedModulesStream(),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          final modules = snapshot.data ?? [];
          return Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  modules.isEmpty
                      ? 'No tienes cámaras vinculadas'
                      : '${modules.length} módulo${modules.length == 1 ? '' : 's'} vinculado${modules.length == 1 ? '' : 's'}',
                  style: GoogleFonts.manrope(
                    fontSize: 13,
                    color: AppTheme.textSecondary,
                  ),
                ),
                const SizedBox(height: 12),
                Expanded(
                  child: modules.isEmpty
                      ? _emptyState()
                      : ListView.separated(
                          itemCount: modules.length,
                          separatorBuilder: (_, __) =>
                              const SizedBox(height: 10),
                          itemBuilder: (_, i) {
                            final data = modules[i];
                            final moduleId =
                                data['module_id'] as String? ?? 'desconocido';
                            return Dismissible(
                              key: ValueKey(moduleId),
                              direction: DismissDirection.endToStart,
                              background: _deleteBackground(),
                              confirmDismiss: (_) => _confirmUnlink(
                                moduleId,
                                data['display_name'] as String?,
                              ),
                              child: _moduleTile(data),
                            );
                          },
                        ),
                ),
                const SizedBox(height: 12),
                ElevatedButton.icon(
                  onPressed: _showLinkDialog,
                  icon: const Icon(Icons.add, size: 20),
                  label: const Text('Vincular nuevo módulo'),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _emptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.videocam_outlined,
              color: AppTheme.iconLight, size: 56),
          const SizedBox(height: 12),
          Text(
            'Aún no has vinculado un módulo',
            style: GoogleFonts.manrope(
              fontSize: 14,
              color: AppTheme.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _deleteBackground() {
    return Container(
      alignment: Alignment.centerRight,
      padding: const EdgeInsets.symmetric(horizontal: 24),
      decoration: BoxDecoration(
        color: AppTheme.alertRed,
        borderRadius: BorderRadius.circular(14),
      ),
      child: const Icon(Icons.link_off, color: Colors.white),
    );
  }

  /// Confirma y desvincula el módulo. Devuelve siempre `false`: la tarjeta no la
  /// quita el Dismissible sino el stream de Firestore al cambiar `user_id`,
  /// evitando el assert "dismissed Dismissible still in tree".
  Future<bool> _confirmUnlink(String moduleId, String? displayName) async {
    final label = displayName ?? moduleId;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(
          'Desvincular módulo',
          style: GoogleFonts.manrope(fontWeight: FontWeight.w700),
        ),
        content: Text(
          'Se detendrá la detección de "$label". ¿Desvincular este módulo?',
          style: GoogleFonts.manrope(fontSize: 14),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancelar'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text(
              'Desvincular',
              style: TextStyle(color: AppTheme.alertRed),
            ),
          ),
        ],
      ),
    );
    if (confirmed != true) return false;

    try {
      await AlertService.unlinkModule(moduleId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Módulo desvinculado')),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('No se pudo desvincular el módulo'),
            backgroundColor: AppTheme.alertRed,
          ),
        );
      }
    }
    return false;
  }

  Future<void> _renameModule(String moduleId, String? currentName) async {
    final controller = TextEditingController(text: currentName ?? '');
    final newName = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(
          'Nombre del módulo',
          style: GoogleFonts.manrope(fontWeight: FontWeight.w700),
        ),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(
            labelText: 'Nombre visible',
            hintText: 'Ej: Sala principal',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancelar'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, controller.text.trim()),
            child: const Text('Guardar'),
          ),
        ],
      ),
    );
    if (newName == null || !mounted) return;
    try {
      await AlertService.renameModule(moduleId, newName);
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('No se pudo actualizar el nombre'),
          backgroundColor: AppTheme.alertRed,
        ),
      );
    }
  }

  /// Sin cámara el módulo no detecta nada, así que eso desplaza a todo lo demás.
  static String _tileSubtitle(
      String? cameraUrl, int cameras, String? displayName, String moduleId) {
    if (cameraUrl == null) return 'Sin cámara configurada';
    final plural = '$cameras cámara${cameras == 1 ? '' : 's'}';
    return displayName != null ? '$plural · $moduleId' : plural;
  }

  Widget _moduleTile(Map<String, dynamic> data) {
    final moduleId = data['module_id'] as String? ?? 'desconocido';
    final displayName = data['display_name'] as String?;
    final status = data['status'] as String? ?? 'disconnected';
    final cameras = (data['cameras'] as List?) ?? [];
    final cameraUrl = data['camera_url'] as String?;
    final isConnected = status == 'connected';
    // Conectado pero ciego: sigue online y no detecta nada.
    final cameraDown = AlertService.isCameraDown(data);
    final isHealthy = isConnected && !cameraDown;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(14),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 10,
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: isHealthy
                  ? AppTheme.primaryContainer
                  : cameraDown
                      ? AppTheme.warningLight
                      : const Color(0xFFF3F3F3),
              borderRadius: BorderRadius.circular(11),
            ),
            child: Icon(
              cameraDown ? Icons.videocam_off_outlined : Icons.videocam_outlined,
              color: isHealthy
                  ? AppTheme.primary
                  : cameraDown
                      ? AppTheme.warning
                      : AppTheme.iconLight,
              size: 22,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  displayName ?? moduleId,
                  style: GoogleFonts.manrope(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  _tileSubtitle(cameraUrl, cameras.length, displayName, moduleId),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.manrope(
                    fontSize: 12,
                    color: cameraUrl == null
                        ? AppTheme.warning
                        : AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          PopupMenuButton<String>(
            icon: const Icon(Icons.more_vert,
                color: AppTheme.iconLight, size: 20),
            tooltip: 'Opciones',
            onSelected: (value) {
              if (value == 'rename') {
                _renameModule(moduleId, displayName);
              } else if (value == 'camera') {
                _changeCamera(moduleId, cameraUrl);
              }
            },
            itemBuilder: (_) => [
              const PopupMenuItem(
                value: 'rename',
                child: ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(Icons.edit_outlined, size: 20),
                  title: Text('Renombrar'),
                ),
              ),
              PopupMenuItem(
                value: 'camera',
                child: ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.videocam_outlined, size: 20),
                  title: Text(cameraUrl == null
                      ? 'Configurar cámara'
                      : 'Cambiar cámara'),
                ),
              ),
            ],
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: isHealthy
                  ? AppTheme.primaryContainer
                  : cameraDown
                      ? AppTheme.warningLight
                      : const Color(0xFFF3F3F3),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              isHealthy
                  ? 'Conectado'
                  : cameraDown
                      ? 'Sin señal'
                      : 'Desconectado',
              style: GoogleFonts.manrope(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color: isHealthy
                    ? AppTheme.primary
                    : cameraDown
                        ? AppTheme.warning
                        : AppTheme.textSecondary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
