import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../theme/app_theme.dart';
import '../services/alert_service.dart';

class LinkedCamerasScreen extends StatefulWidget {
  const LinkedCamerasScreen({super.key});

  @override
  State<LinkedCamerasScreen> createState() => _LinkedCamerasScreenState();
}

class _LinkedCamerasScreenState extends State<LinkedCamerasScreen> {
  Future<void> _showLinkDialog() async {
    final idController = TextEditingController();
    final nameController = TextEditingController();
    final result = await showDialog<(String, String)>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(
          'Vincular nuevo módulo',
          style: GoogleFonts.manrope(fontWeight: FontWeight.w700),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: idController,
              autofocus: true,
              decoration: const InputDecoration(
                labelText: 'ID del módulo',
                hintText: 'FG-XXXX-XXXX',
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: nameController,
              decoration: const InputDecoration(
                labelText: 'Nombre visible (opcional)',
                hintText: 'Ej: Sala principal',
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancelar'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(
              ctx,
              (idController.text.trim(), nameController.text.trim()),
            ),
            child: const Text('Vincular'),
          ),
        ],
      ),
    );
    if (result == null || result.$1.isEmpty || !mounted) return;
    final moduleId = result.$1;
    final displayName = result.$2;

    try {
      await AlertService.linkModule(moduleId);
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('No se pudo vincular el módulo. Verifica el ID.'),
          backgroundColor: AppTheme.alertRed,
        ),
      );
      return;
    }

    // Vinculado correctamente — asignar el nombre si se ingresó uno
    if (displayName.isNotEmpty) {
      try {
        await AlertService.renameModule(moduleId, displayName);
      } catch (_) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
                'Módulo vinculado, pero no se pudo guardar el nombre. Edítalo luego.'),
            backgroundColor: AppTheme.alertRed,
          ),
        );
        return;
      }
    }

    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Módulo vinculado correctamente')),
    );
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

  Widget _moduleTile(Map<String, dynamic> data) {
    final moduleId = data['module_id'] as String? ?? 'desconocido';
    final displayName = data['display_name'] as String?;
    final status = data['status'] as String? ?? 'disconnected';
    final cameras = (data['cameras'] as List?) ?? [];
    final isConnected = status == 'connected';

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
              color: isConnected
                  ? AppTheme.primaryContainer
                  : const Color(0xFFF3F3F3),
              borderRadius: BorderRadius.circular(11),
            ),
            child: Icon(
              Icons.videocam_outlined,
              color: isConnected ? AppTheme.primary : AppTheme.iconLight,
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
                  displayName != null
                      ? '${cameras.length} cámara${cameras.length == 1 ? '' : 's'} · $moduleId'
                      : '${cameras.length} cámara${cameras.length == 1 ? '' : 's'}',
                  style: GoogleFonts.manrope(
                    fontSize: 12,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.edit_outlined,
                color: AppTheme.iconLight, size: 20),
            onPressed: () => _renameModule(moduleId, displayName),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: isConnected
                  ? AppTheme.primaryContainer
                  : const Color(0xFFF3F3F3),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              isConnected ? 'Conectado' : 'Desconectado',
              style: GoogleFonts.manrope(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color:
                    isConnected ? AppTheme.primary : AppTheme.textSecondary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
