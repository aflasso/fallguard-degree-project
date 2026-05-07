import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../theme/app_theme.dart';
import '../widgets/fallguard_app_bar.dart';
import '../services/auth_service.dart';
import 'edit_profile_screen.dart';
import 'security_screen.dart';
import 'emergency_alerts_screen.dart';
import 'assisted_persons_screen.dart';
import 'linked_cameras_screen.dart';
import 'help_center_screen.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  void _open(BuildContext context, Widget screen) {
    Navigator.push(context, MaterialPageRoute(builder: (_) => screen));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: const FallGuardAppBar(showAvatar: false),
      body: SingleChildScrollView(
        child: Column(
          children: [
            const SizedBox(height: 24),

            // ── Profile section ────────────────────────────────────────
            GestureDetector(
              onTap: () => _open(context, const EditProfileScreen()),
              child: Stack(
                alignment: Alignment.center,
                children: [
                  Container(
                    width: 90,
                    height: 90,
                    decoration: BoxDecoration(
                      color: AppTheme.primaryContainer,
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: AppTheme.primary.withValues(alpha: 0.2),
                        width: 3,
                      ),
                    ),
                    child: const Icon(
                      Icons.person,
                      size: 48,
                      color: AppTheme.primary,
                    ),
                  ),
                  Positioned(
                    bottom: 0,
                    right: 0,
                    child: Container(
                      width: 28,
                      height: 28,
                      decoration: BoxDecoration(
                        color: AppTheme.primary,
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white, width: 2),
                      ),
                      child: const Icon(
                        Icons.edit,
                        color: Colors.white,
                        size: 14,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            Text(
              AuthService.currentUser?.displayName ?? 'Usuario',
              style: GoogleFonts.manrope(
                fontSize: 22,
                fontWeight: FontWeight.w800,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              AuthService.currentUser?.email ?? '',
              style: GoogleFonts.manrope(
                fontSize: 13,
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: 160,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  minimumSize: const Size(160, 44),
                  padding: EdgeInsets.zero,
                ),
                onPressed: () => _open(context, const EditProfileScreen()),
                child: Text(
                  'Editar Perfil',
                  style: GoogleFonts.manrope(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 28),

            // ── Sections ───────────────────────────────────────────────
            _section('SEGURIDAD DE LA CUENTA', [
              _Item(
                Icons.lock_outline,
                'Seguridad y Contraseña',
                'Actualiza credenciales y 2FA',
                () => _open(context, const SecurityScreen()),
              ),
              _Item(
                Icons.notifications_outlined,
                'Alertas de Emergencia',
                'Gestiona sirena y contactos SMS',
                () => _open(context, const EmergencyAlertsScreen()),
              ),
            ]),
            const SizedBox(height: 20),
            _section('MONITOREO', [
              _Item(
                Icons.people_outline,
                'Personas Asistidas',
                'Gestiona los perfiles monitoreados',
                () => _open(context, const AssistedPersonsScreen()),
              ),
              _Item(
                Icons.videocam_outlined,
                'Cámaras Vinculadas',
                'Administra los módulos conectados',
                () => _open(context, const LinkedCamerasScreen()),
              ),
            ]),
            const SizedBox(height: 20),
            _section('SOPORTE', [
              _Item(
                Icons.help_outline,
                'Centro de Ayuda',
                'Guías y soporte técnico',
                () => _open(context, const HelpCenterScreen()),
              ),
            ]),
            const SizedBox(height: 24),

            // ── Logout ─────────────────────────────────────────────────
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: GestureDetector(
                onTap: () => AuthService.signOut(),
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF3F3F3),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.logout,
                          color: AppTheme.alertRed, size: 18),
                      const SizedBox(width: 8),
                      Text(
                        'Cerrar sesión',
                        style: GoogleFonts.manrope(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.alertRed,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              'VERSIÓN 2.4.0 (GOLD-BUILD)',
              style: GoogleFonts.manrope(
                fontSize: 11,
                color: AppTheme.iconLight,
                letterSpacing: 0.5,
              ),
            ),
            const SizedBox(height: 28),
          ],
        ),
      ),
    );
  }

  Widget _section(String title, List<_Item> items) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(left: 4, bottom: 8),
            child: Text(
              title,
              style: GoogleFonts.manrope(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color: AppTheme.textSecondary,
                letterSpacing: 0.8,
              ),
            ),
          ),
          Container(
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
            child: Column(
              children: items.asMap().entries.map((entry) {
                final isLast = entry.key == items.length - 1;
                return Column(
                  children: [
                    _row(entry.value),
                    if (!isLast)
                      const Padding(
                        padding: EdgeInsets.symmetric(horizontal: 16),
                        child: Divider(
                            height: 1, color: AppTheme.divider),
                      ),
                  ],
                );
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _row(_Item item) {
    return InkWell(
      onTap: item.onTap,
      borderRadius: BorderRadius.circular(14),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: AppTheme.background,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(item.icon,
                  color: AppTheme.textSecondary, size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.title,
                    style: GoogleFonts.manrope(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  Text(
                    item.subtitle,
                    style: GoogleFonts.manrope(
                      fontSize: 12,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(Icons.chevron_right,
                color: AppTheme.iconLight, size: 20),
          ],
        ),
      ),
    );
  }
}

class _Item {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  const _Item(this.icon, this.title, this.subtitle, this.onTap);
}
