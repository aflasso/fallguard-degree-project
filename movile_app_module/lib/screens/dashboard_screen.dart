import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../theme/app_theme.dart';
import '../services/auth_service.dart';
import '../services/alert_service.dart';
import '../models/alert_model.dart';
import '../widgets/fallguard_app_bar.dart';
import 'linked_cameras_screen.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key, this.onSeeAllHistory});

  /// Cambia a la pestaña de Historial (provisto por HomeWrapper).
  final VoidCallback? onSeeAllHistory;

  /// Estado del header según (en orden de prioridad):
  /// 1. alertas sin confirmar, 2. sin módulos vinculados,
  /// 3. algún módulo vinculado desconectado, 4. algún módulo conectado pero
  /// con la cámara sin señal, 5. todo en orden.
  ///
  /// Desconectado va antes que cámara sin señal porque es el fallo más
  /// ambiguo: no sabemos si el módulo sigue vivo detectando y encolando
  /// alertas, o si está apagado. Con la cámara caída sabemos exactamente qué
  /// pasa — el módulo vive y no ve.
  ({String label, Color accent, Color container, IconData icon}) _headerState({
    required int pendingAlerts,
    required bool hasModules,
    required bool anyDisconnected,
    required bool anyCameraDown,
  }) {
    if (pendingAlerts > 0) {
      return (
        label: pendingAlerts == 1
            ? '1 alerta sin confirmar'
            : '$pendingAlerts alertas sin confirmar',
        accent: AppTheme.alertRed,
        container: AppTheme.alertRedLight,
        icon: Icons.priority_high_rounded,
      );
    }
    if (!hasModules) {
      return (
        label: 'Sin módulos vinculados',
        accent: AppTheme.textSecondary,
        container: const Color(0xFFF1F3F5),
        icon: Icons.link_off_rounded,
      );
    }
    if (anyDisconnected) {
      return (
        label: 'Módulo desconectado',
        accent: AppTheme.warning,
        container: AppTheme.warningLight,
        icon: Icons.wifi_off_rounded,
      );
    }
    if (anyCameraDown) {
      return (
        label: 'Cámara sin señal',
        accent: AppTheme.warning,
        container: AppTheme.warningLight,
        icon: Icons.videocam_off_rounded,
      );
    }
    return (
      label: 'Protección Activa',
      accent: AppTheme.primary,
      container: AppTheme.primaryContainer,
      icon: Icons.check_rounded,
    );
  }

  // ── Header (texto + nombre + avatar con badge de estado) ──────────────────
  Widget _header(
      ({String label, Color accent, Color container, IconData icon}) st) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                st.label,
                style: GoogleFonts.manrope(
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                  color: st.accent,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                AuthService.currentUser?.displayName ?? 'Paciente',
                style: GoogleFonts.manrope(
                  fontSize: 26,
                  fontWeight: FontWeight.w800,
                  color: AppTheme.textPrimary,
                ),
              ),
            ],
          ),
        ),
        Stack(
          children: [
            Container(
              width: 68,
              height: 68,
              decoration: BoxDecoration(
                color: st.container,
                shape: BoxShape.circle,
                border: Border.all(
                  color: st.accent.withValues(alpha: 0.25),
                  width: 2.5,
                ),
              ),
              child: Icon(Icons.elderly, size: 36, color: st.accent),
            ),
            Positioned(
              bottom: 0,
              right: 0,
              child: Container(
                width: 22,
                height: 22,
                decoration: BoxDecoration(
                  color: st.accent,
                  shape: BoxShape.circle,
                ),
                child: Icon(st.icon, color: Colors.white, size: 12),
              ),
            ),
          ],
        ),
      ],
    );
  }

  // ── Tarjeta de estado dinámica (misma prioridad que el header) ────────────
  Widget _statusCard(
    BuildContext context, {
    required List<AlertModel> pendingList,
    required bool hasModules,
    required List<Map<String, dynamic>> disconnected,
    required List<Map<String, dynamic>> cameraDown,
  }) {
    if (pendingList.isNotEmpty) return _alertsPreviewCard(context, pendingList);
    if (!hasModules) return _noModulesCard(context);
    if (disconnected.isNotEmpty) return _disconnectedCard(disconnected);
    if (cameraDown.isNotEmpty) return _cameraDownCard(cameraDown);
    return _safeCard();
  }

  BoxDecoration _cardDecoration({Color? border}) => BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(18),
        border: border != null ? Border.all(color: border) : null,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 14,
            offset: const Offset(0, 2),
          ),
        ],
      );

  // Estado seguro — todo en orden
  Widget _safeCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 28, horizontal: 20),
      decoration: _cardDecoration(),
      child: Column(
        children: [
          Container(
            width: 64,
            height: 64,
            decoration: const BoxDecoration(
              color: AppTheme.primary,
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.check_circle_outline,
                color: Colors.white, size: 32),
          ),
          const SizedBox(height: 16),
          Text(
            'Estado: Seguro',
            style: GoogleFonts.manrope(
              fontSize: 20,
              fontWeight: FontWeight.w800,
              color: AppTheme.primary,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Sin caídas detectadas hoy',
            style: GoogleFonts.manrope(
              fontSize: 13,
              color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
            decoration: BoxDecoration(
              color: AppTheme.primaryContainer,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 7,
                  height: 7,
                  decoration: const BoxDecoration(
                    color: AppTheme.primary,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 6),
                Text(
                  'Monitoreo en tiempo real activo',
                  style: GoogleFonts.manrope(
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                    color: AppTheme.primary,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // Hay alertas sin confirmar — preview de acceso rápido
  Widget _alertsPreviewCard(BuildContext context, List<AlertModel> pending) {
    final preview = pending.take(3).toList();
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration(border: AppTheme.alertRedLight),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.notifications_active_rounded,
                  color: AppTheme.alertRed, size: 20),
              const SizedBox(width: 8),
              Text(
                'Alertas por revisar',
                style: GoogleFonts.manrope(
                  fontSize: 15,
                  fontWeight: FontWeight.w800,
                  color: AppTheme.textPrimary,
                ),
              ),
              const Spacer(),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 9, vertical: 2),
                decoration: BoxDecoration(
                  color: AppTheme.alertRed,
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  '${pending.length}',
                  style: GoogleFonts.manrope(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          ...preview.map((a) => _alertPreviewRow(context, a)),
          if (pending.length > preview.length) ...[
            const SizedBox(height: 6),
            Text(
              'y ${pending.length - preview.length} alerta(s) más por revisar',
              style: GoogleFonts.manrope(
                fontSize: 12,
                color: AppTheme.textSecondary,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _alertPreviewRow(BuildContext context, AlertModel a) {
    final ts = a.timestamp;
    final time =
        '${ts.day}/${ts.month} · ${ts.hour}:${ts.minute.toString().padLeft(2, '0')}';
    final subtitle = a.location.isNotEmpty ? '${a.location} · $time' : time;
    return InkWell(
      onTap: () => Navigator.pushNamed(
        context,
        '/emergency',
        arguments: {
          'alertId': a.id,
          'timestamp': a.timestamp.toIso8601String(),
          'status': a.status.name,
        },
      ),
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(
          children: [
            Container(
              width: 38,
              height: 38,
              decoration: BoxDecoration(
                color: AppTheme.alertRedLight,
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.warning_amber_rounded,
                  color: AppTheme.alertRed, size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Caída detectada',
                    style: GoogleFonts.manrope(
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    subtitle,
                    style: GoogleFonts.manrope(
                      fontSize: 12,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(Icons.chevron_right, color: AppTheme.iconLight, size: 20),
          ],
        ),
      ),
    );
  }

  // Hay módulos vinculados pero alguno desconectado
  Widget _disconnectedCard(List<Map<String, dynamic>> disconnected) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration(border: AppTheme.warningLight),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.wifi_off_rounded,
                  color: AppTheme.warning, size: 20),
              const SizedBox(width: 8),
              Text(
                disconnected.length == 1
                    ? 'Módulo desconectado'
                    : 'Módulos desconectados',
                style: GoogleFonts.manrope(
                  fontSize: 15,
                  fontWeight: FontWeight.w800,
                  color: AppTheme.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          ...disconnected.map(_disconnectedModuleRow),
        ],
      ),
    );
  }

  // El módulo está online pero ciego: no va a detectar nada aunque la app
  // lo muestre conectado.
  Widget _cameraDownCard(List<Map<String, dynamic>> cameraDown) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration(border: AppTheme.warningLight),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.videocam_off_rounded,
                  color: AppTheme.warning, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  cameraDown.length == 1
                      ? 'Cámara sin señal'
                      : 'Cámaras sin señal',
                  style: GoogleFonts.manrope(
                    fontSize: 15,
                    fontWeight: FontWeight.w800,
                    color: AppTheme.textPrimary,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            'El módulo está conectado pero no recibe imagen. '
            'No se detectarán caídas hasta que se restablezca.',
            style: GoogleFonts.manrope(
              fontSize: 12,
              color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(height: 6),
          ...cameraDown.map(_cameraDownModuleRow),
        ],
      ),
    );
  }

  Widget _cameraDownModuleRow(Map<String, dynamic> data) {
    final moduleId = data['module_id'] as String? ?? 'desconocido';
    final displayName = data['display_name'] as String?;

    final sinceRaw = data['camera_status_at'];
    DateTime? since;
    if (sinceRaw is Timestamp) {
      since = sinceRaw.toDate();
    } else if (sinceRaw is String) {
      since = DateTime.tryParse(sinceRaw);
    }
    final String info;
    if (since != null) {
      final l = since.toLocal();
      info =
          'Sin imagen desde ${l.day}/${l.month}/${l.year} · ${l.hour}:${l.minute.toString().padLeft(2, '0')}';
    } else {
      info = 'Sin imagen';
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: AppTheme.warningLight,
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.videocam_off_outlined,
                color: AppTheme.warning, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  displayName ?? moduleId,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.manrope(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  info,
                  style: GoogleFonts.manrope(
                    fontSize: 11,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _disconnectedModuleRow(Map<String, dynamic> data) {
    final moduleId = data['module_id'] as String? ?? 'desconocido';
    final displayName = data['display_name'] as String?;

    final lastSeenRaw = data['last_seen'];
    DateTime? lastSeen;
    if (lastSeenRaw is Timestamp) {
      lastSeen = lastSeenRaw.toDate();
    } else if (lastSeenRaw is String) {
      lastSeen = DateTime.tryParse(lastSeenRaw);
    }
    final String connInfo;
    if (lastSeen != null) {
      final l = lastSeen.toLocal();
      connInfo =
          'Última conexión: ${l.day}/${l.month}/${l.year} · ${l.hour}:${l.minute.toString().padLeft(2, '0')}';
    } else {
      connInfo = 'En espera · sin conexión previa';
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: AppTheme.warningLight,
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.videocam_off_outlined,
                color: AppTheme.warning, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  displayName ?? moduleId,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.manrope(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                if (displayName != null)
                  Text(
                    moduleId,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: GoogleFonts.manrope(
                      fontSize: 11,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                Text(
                  connInfo,
                  style: GoogleFonts.manrope(
                    fontSize: 11,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // No hay módulos vinculados — invitación + acceso rápido
  Widget _noModulesCard(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 28, horizontal: 20),
      decoration: _cardDecoration(),
      child: Column(
        children: [
          Container(
            width: 64,
            height: 64,
            decoration: const BoxDecoration(
              color: Color(0xFFF1F3F5),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.videocam_off_outlined,
                color: AppTheme.textSecondary, size: 32),
          ),
          const SizedBox(height: 16),
          Text(
            'Sin módulos vinculados',
            style: GoogleFonts.manrope(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Vincula un módulo para empezar a monitorear caídas en tiempo real.',
            textAlign: TextAlign.center,
            style: GoogleFonts.manrope(
              fontSize: 13,
              color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const LinkedCamerasScreen()),
            ),
            icon: const Icon(Icons.add, size: 20),
            label: const Text('Vincular módulo'),
          ),
        ],
      ),
    );
  }

  // ── Historial reciente ────────────────────────────────────────────────────
  ({String label, Color color, Color bg, IconData icon}) _alertVisual(
      AlertStatus status) {
    switch (status) {
      case AlertStatus.detected:
        return (
          label: 'Caída sin confirmar',
          color: AppTheme.alertRed,
          bg: AppTheme.alertRedLight,
          icon: Icons.warning_amber_rounded,
        );
      case AlertStatus.confirmed:
        return (
          label: 'Caída confirmada',
          color: const Color(0xFF2E7D32),
          bg: const Color(0xFFE8F5E9),
          icon: Icons.check_circle_outline,
        );
      case AlertStatus.falseAlarm:
        return (
          label: 'Falsa alarma',
          color: AppTheme.textSecondary,
          bg: const Color(0xFFF1F3F5),
          icon: Icons.cancel_outlined,
        );
    }
  }

  Widget _historyRow(BuildContext context, AlertModel a) {
    final v = _alertVisual(a.status);
    final ts = a.timestamp;
    final date = '${ts.day}/${ts.month}/${ts.year}';
    final time = '${ts.hour}:${ts.minute.toString().padLeft(2, '0')}';
    return InkWell(
      onTap: () => Navigator.pushNamed(
        context,
        '/emergency',
        arguments: {
          'alertId': a.id,
          'timestamp': a.timestamp.toIso8601String(),
          'status': a.status.name,
        },
      ),
      borderRadius: BorderRadius.circular(14),
      child: Container(
        padding: const EdgeInsets.all(14),
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
              width: 42,
              height: 42,
              decoration: BoxDecoration(
                color: v.bg,
                borderRadius: BorderRadius.circular(11),
              ),
              child: Icon(v.icon, color: v.color, size: 22),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    v.label,
                    style: GoogleFonts.manrope(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '$date · $time',
                    style: GoogleFonts.manrope(
                      fontSize: 12,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(Icons.chevron_right, color: AppTheme.iconLight, size: 20),
          ],
        ),
      ),
    );
  }

  Widget _emptyHistoryCard() {
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
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: AppTheme.primaryContainer,
              borderRadius: BorderRadius.circular(11),
            ),
            child: const Icon(Icons.check_circle_outline,
                color: AppTheme.primary, size: 22),
          ),
          const SizedBox(width: 12),
          Text(
            'Sin alertas recientes',
            style: GoogleFonts.manrope(
              fontSize: 14,
              color: AppTheme.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: FallGuardAppBar(
        onBellTap: () => Navigator.pushNamed(context, '/emergency'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Patient Header (estado dinámico) ───────────────────────
            StreamBuilder<List<AlertModel>>(
              stream: AlertService.alertsStream(),
              builder: (context, alertSnap) {
                final pendingList = (alertSnap.data ?? [])
                    .where((a) => a.status == AlertStatus.detected)
                    .toList();
                return StreamBuilder<List<Map<String, dynamic>>>(
                  stream: AlertService.linkedModulesStream(),
                  builder: (context, modSnap) {
                    final modules = modSnap.data ?? [];
                    final hasModules = modules.isNotEmpty;
                    final disconnected = modules
                        .where((m) => (m['status'] as String?) != 'connected')
                        .toList();
                    final cameraDown =
                        modules.where(AlertService.isCameraDown).toList();
                    final st = _headerState(
                      pendingAlerts: pendingList.length,
                      hasModules: hasModules,
                      anyDisconnected: disconnected.isNotEmpty,
                      anyCameraDown: cameraDown.isNotEmpty,
                    );
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _header(st),
                        const SizedBox(height: 20),
                        _statusCard(
                          context,
                          pendingList: pendingList,
                          hasModules: hasModules,
                          disconnected: disconnected,
                          cameraDown: cameraDown,
                        ),
                      ],
                    );
                  },
                );
              },
            ),
            const SizedBox(height: 24),

            // ── Security History Header ────────────────────────────────
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Historial de Seguridad',
                  style: GoogleFonts.manrope(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  ),
                ),
                TextButton(
                  onPressed: onSeeAllHistory,
                  style: TextButton.styleFrom(
                    padding: EdgeInsets.zero,
                    minimumSize: Size.zero,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                  child: Text(
                    'Ver todo',
                    style: GoogleFonts.manrope(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.primary,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),

            // ── Historial reciente (tiempo real) ───────────────────────
            StreamBuilder<List<AlertModel>>(
              stream: AlertService.alertsStream(),
              builder: (context, snapshot) {
                final alerts = snapshot.data ?? [];
                if (alerts.isEmpty) return _emptyHistoryCard();
                final recent = alerts.take(4).toList();
                return Column(
                  children: [
                    for (int i = 0; i < recent.length; i++) ...[
                      if (i > 0) const SizedBox(height: 10),
                      _historyRow(context, recent[i]),
                    ],
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
