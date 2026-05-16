import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../theme/app_theme.dart';
import '../models/alert_model.dart';
import '../services/alert_service.dart';
import '../widgets/fallguard_app_bar.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  int _selectedFilter = 0;

  static const List<String> _filters = [
    'Todos',
    'Sin confirmar',
    'Confirmadas',
    'Falsas alarmas',
  ];

  static const List<String> _months = [
    'ene', 'feb', 'mar', 'abr', 'may', 'jun',
    'jul', 'ago', 'sep', 'oct', 'nov', 'dic',
  ];

  String _formatDate(DateTime date) {
    return '${date.day.toString().padLeft(2, '0')} '
        '${_months[date.month - 1]} '
        '${date.year}';
  }

  String _formatTime(DateTime date) {
    final h = date.hour > 12
        ? date.hour - 12
        : (date.hour == 0 ? 12 : date.hour);
    final m = date.minute.toString().padLeft(2, '0');
    final ampm = date.hour >= 12 ? 'PM' : 'AM';
    return '${h.toString().padLeft(2, '0')}:$m $ampm';
  }

  List<AlertModel> _applyFilter(List<AlertModel> alerts) {
    switch (_selectedFilter) {
      case 1:
        return alerts.where((a) => a.status == AlertStatus.detected).toList();
      case 2:
        return alerts.where((a) => a.status == AlertStatus.confirmed).toList();
      case 3:
        return alerts.where((a) => a.status == AlertStatus.falseAlarm).toList();
      default:
        return alerts;
    }
  }

  void _openAlert(AlertModel alert) {
    Navigator.pushNamed(
      context,
      '/emergency',
      arguments: {
        'alertId':   alert.id,
        'timestamp': alert.timestamp.toIso8601String(),
        'status':    alert.status.name,
      },
    );
  }

  Future<void> _deleteAlert(AlertModel alert) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppTheme.surface,
        title: Text(
          'Eliminar alerta',
          style: GoogleFonts.manrope(
            fontWeight: FontWeight.w700,
            color: AppTheme.textPrimary,
          ),
        ),
        content: Text(
          '¿Eliminar el registro del ${_formatDate(alert.timestamp)}?',
          style: GoogleFonts.manrope(color: AppTheme.textSecondary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text('Cancelar',
                style: GoogleFonts.manrope(color: AppTheme.textSecondary)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text('Eliminar',
                style: GoogleFonts.manrope(
                    color: AppTheme.alertRed, fontWeight: FontWeight.w700)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await AlertService.deleteAlert(alert.id);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error al eliminar: $e')),
        );
      }
    }
  }

  Future<void> _deleteAll() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppTheme.surface,
        title: Text(
          'Eliminar todo el historial',
          style: GoogleFonts.manrope(
            fontWeight: FontWeight.w700,
            color: AppTheme.textPrimary,
          ),
        ),
        content: Text(
          'Se eliminarán todas las alertas registradas. Esta acción no se puede deshacer.',
          style: GoogleFonts.manrope(color: AppTheme.textSecondary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text('Cancelar',
                style: GoogleFonts.manrope(color: AppTheme.textSecondary)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text('Eliminar todo',
                style: GoogleFonts.manrope(
                    color: AppTheme.alertRed, fontWeight: FontWeight.w700)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await AlertService.deleteAllAlerts();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error al eliminar: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: const FallGuardAppBar(),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Page Header ──────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Historial de Alertas',
                        style: GoogleFonts.manrope(
                          fontSize: 26,
                          fontWeight: FontWeight.w800,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Revisa y gestiona los eventos pasados de detección de caídas.',
                        style: GoogleFonts.manrope(
                          fontSize: 13,
                          color: AppTheme.textSecondary,
                          height: 1.4,
                        ),
                      ),
                    ],
                  ),
                ),
                // Botón eliminar todo
                IconButton(
                  onPressed: _deleteAll,
                  icon: const Icon(Icons.delete_sweep_outlined),
                  color: AppTheme.textSecondary,
                  tooltip: 'Eliminar todo el historial',
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // ── Filter Chips ─────────────────────────────────────────────
          SizedBox(
            height: 38,
            child: ListView.separated(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              scrollDirection: Axis.horizontal,
              itemCount: _filters.length,
              separatorBuilder: (_, __) => const SizedBox(width: 8),
              itemBuilder: (context, index) {
                final selected = _selectedFilter == index;
                return GestureDetector(
                  onTap: () => setState(() => _selectedFilter = index),
                  child: Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 16, vertical: 7),
                    decoration: BoxDecoration(
                      color: selected ? AppTheme.primary : AppTheme.surface,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: selected ? AppTheme.primary : AppTheme.divider,
                      ),
                    ),
                    child: Text(
                      _filters[index],
                      style: GoogleFonts.manrope(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color:
                            selected ? Colors.white : AppTheme.textSecondary,
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 16),

          // ── Alert List ───────────────────────────────────────────────
          Expanded(
            child: StreamBuilder<List<AlertModel>>(
              stream: AlertService.alertsStream(),
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Center(child: CircularProgressIndicator());
                }
                final alerts = _applyFilter(snapshot.data ?? []);
                return ListView.separated(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  itemCount: alerts.length + 1,
                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                  itemBuilder: (context, index) {
                    if (index == alerts.length) {
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 28),
                        child: Column(
                          children: [
                            const Icon(Icons.access_time_outlined,
                                color: AppTheme.iconLight, size: 30),
                            const SizedBox(height: 8),
                            Text(
                              alerts.isEmpty
                                  ? 'Sin alertas registradas'
                                  : 'No hay más alertas registradas',
                              style: GoogleFonts.manrope(
                                  fontSize: 13, color: AppTheme.iconLight),
                            ),
                          ],
                        ),
                      );
                    }
                    final alert = alerts[index];
                    return _AlertTile(
                      alert: alert,
                      dateLabel: _formatDate(alert.timestamp),
                      timeLabel: _formatTime(alert.timestamp),
                      onTap: () => _openAlert(alert),
                      onDelete: () => _deleteAlert(alert),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _AlertTile extends StatelessWidget {
  final AlertModel alert;
  final String dateLabel;
  final String timeLabel;
  final VoidCallback onTap;
  final VoidCallback onDelete;

  const _AlertTile({
    required this.alert,
    required this.dateLabel,
    required this.timeLabel,
    required this.onTap,
    required this.onDelete,
  });

  Color get _badgeColor {
    return switch (alert.status) {
      AlertStatus.confirmed  => const Color(0xFFE8F5E9),
      AlertStatus.falseAlarm => const Color(0xFFF5F5F5),
      _                      => AppTheme.alertRedLight,
    };
  }

  Color get _badgeTextColor {
    return switch (alert.status) {
      AlertStatus.confirmed  => const Color(0xFF2E7D32),
      AlertStatus.falseAlarm => AppTheme.textSecondary,
      _                      => AppTheme.alertRed,
    };
  }

  IconData get _statusIcon {
    return switch (alert.status) {
      AlertStatus.confirmed  => Icons.check_circle_outline,
      AlertStatus.falseAlarm => Icons.cancel_outlined,
      _                      => Icons.warning_amber_rounded,
    };
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
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
            // Icon
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: _badgeColor,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(_statusIcon, color: _badgeTextColor, size: 22),
            ),
            const SizedBox(width: 12),

            // Date & time
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    dateLabel,
                    style: GoogleFonts.manrope(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    timeLabel,
                    style: GoogleFonts.manrope(
                      fontSize: 13,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),
            ),

            // Status badge
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: _badgeColor,
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                alert.statusLabel,
                style: GoogleFonts.manrope(
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                  color: _badgeTextColor,
                ),
              ),
            ),
            const SizedBox(width: 4),

            // Actions menu
            PopupMenuButton<String>(
              icon: const Icon(Icons.more_vert,
                  color: AppTheme.iconLight, size: 20),
              color: AppTheme.surface,
              onSelected: (value) {
                if (value == 'delete') onDelete();
              },
              itemBuilder: (_) => [
                PopupMenuItem(
                    value: 'delete',
                    child: Row(
                      children: [
                        const Icon(Icons.delete_outline,
                            size: 18, color: AppTheme.alertRed),
                        const SizedBox(width: 8),
                        Text('Eliminar',
                            style: GoogleFonts.manrope(
                                color: AppTheme.alertRed)),
                      ],
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
