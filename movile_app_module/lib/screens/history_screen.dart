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
    'Confirmadas',
    'Descartadas',
    'Últimas 30 días',
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

  List<AlertModel> _applyFilter(List<AlertModel> alerts) {
    final now = DateTime.now();
    switch (_selectedFilter) {
      case 1:
        return alerts.where((a) => a.status == AlertStatus.confirmed).toList();
      case 2:
        return alerts.where((a) => a.status == AlertStatus.dismissed).toList();
      case 3:
        return alerts
            .where((a) => a.timestamp
                .isAfter(now.subtract(const Duration(days: 30))))
            .toList();
      default:
        return alerts;
    }
  }

  String _formatTime(DateTime date) {
    final h = date.hour > 12
        ? date.hour - 12
        : (date.hour == 0 ? 12 : date.hour);
    final m = date.minute.toString().padLeft(2, '0');
    final ampm = date.hour >= 12 ? 'PM' : 'AM';
    return '${h.toString().padLeft(2, '0')}:$m $ampm';
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
                const SizedBox(height: 16),
              ],
            ),
          ),

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
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 7),
                    decoration: BoxDecoration(
                      color:
                          selected ? AppTheme.primary : AppTheme.surface,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color:
                            selected ? AppTheme.primary : AppTheme.divider,
                      ),
                    ),
                    child: Text(
                      _filters[index],
                      style: GoogleFonts.manrope(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: selected
                            ? Colors.white
                            : AppTheme.textSecondary,
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
                            const Icon(
                              Icons.access_time_outlined,
                              color: AppTheme.iconLight,
                              size: 30,
                            ),
                            const SizedBox(height: 8),
                            Text(
                              alerts.isEmpty
                                  ? 'Sin alertas registradas'
                                  : 'No hay más alertas registradas',
                              style: GoogleFonts.manrope(
                                fontSize: 13,
                                color: AppTheme.iconLight,
                              ),
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

  const _AlertTile({
    required this.alert,
    required this.dateLabel,
    required this.timeLabel,
  });

  @override
  Widget build(BuildContext context) {
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
          // Icon
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppTheme.alertRedLight,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(
              Icons.refresh,
              color: AppTheme.alertRed,
              size: 22,
            ),
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
          // Status badge + chevron
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: AppTheme.alertRedLight,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  alert.statusLabel,
                  style: GoogleFonts.manrope(
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.alertRed,
                  ),
                ),
              ),
              const SizedBox(height: 8),
              const Icon(Icons.chevron_right,
                  color: AppTheme.iconLight, size: 20),
            ],
          ),
        ],
      ),
    );
  }
}
