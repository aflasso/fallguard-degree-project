import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../theme/app_theme.dart';

class HelpCenterScreen extends StatelessWidget {
  const HelpCenterScreen({super.key});

  static const List<_Faq> _faqs = [
    _Faq(
      '¿Cómo vinculo mi cámara FallGuard?',
      'Ve a Ajustes → Cámaras Vinculadas y toca "Vincular nuevo módulo". '
          'Ingresa el ID del módulo (FG-XXXX-XXXX) o escanea el código QR '
          'que viene con el dispositivo.',
    ),
    _Faq(
      '¿Qué hago si recibo una alerta de caída?',
      'La app abrirá automáticamente la pantalla de emergencia. Puedes '
          'confirmar la caída para alertar a los contactos de emergencia o '
          'descartarla si fue una falsa alarma.',
    ),
    _Faq(
      '¿Mi cámara dejó de monitorear?',
      'Verifica que el módulo tenga conexión a internet y energía. En la '
          'pantalla principal verás el estado del monitoreo en tiempo real.',
    ),
    _Faq(
      '¿Cómo cambio mi contraseña?',
      'Ve a Ajustes → Seguridad y Contraseña. Ingresa tu contraseña actual '
          'y la nueva. También puedes recibir un correo de restablecimiento.',
    ),
    _Faq(
      '¿Las notificaciones no llegan?',
      'Asegúrate de tener permisos de notificación habilitados para '
          'FallGuard en los ajustes del sistema y de tener conexión a internet.',
    ),
  ];

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
          'Centro de Ayuda',
          style: GoogleFonts.manrope(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: AppTheme.textPrimary,
          ),
        ),
        centerTitle: true,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '¿Cómo podemos ayudarte?',
              style: GoogleFonts.manrope(
                fontSize: 22,
                fontWeight: FontWeight.w800,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'Encuentra respuestas a las preguntas más frecuentes o '
              'contáctanos directamente.',
              style: GoogleFonts.manrope(
                fontSize: 13,
                color: AppTheme.textSecondary,
                height: 1.4,
              ),
            ),
            const SizedBox(height: 24),
            _sectionTitle('PREGUNTAS FRECUENTES'),
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
                children: _faqs
                    .asMap()
                    .entries
                    .expand((e) => [
                          _FaqTile(faq: e.value),
                          if (e.key != _faqs.length - 1)
                            const Divider(
                                height: 1, color: AppTheme.divider),
                        ])
                    .toList(),
              ),
            ),
            const SizedBox(height: 24),
            _sectionTitle('CONTACTO'),
            _contactRow(
              icon: Icons.mail_outline,
              title: 'Correo de soporte',
              subtitle: 'soporte@fallguard.app',
            ),
            const SizedBox(height: 10),
            _contactRow(
              icon: Icons.phone_outlined,
              title: 'Línea de atención',
              subtitle: '+57 1 800 555 0199',
            ),
            const SizedBox(height: 10),
            _contactRow(
              icon: Icons.chat_bubble_outline,
              title: 'Chat en vivo',
              subtitle: 'Lunes a viernes, 8am - 6pm',
            ),
            const SizedBox(height: 28),
          ],
        ),
      ),
    );
  }

  Widget _sectionTitle(String text) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 8),
      child: Text(
        text,
        style: GoogleFonts.manrope(
          fontSize: 11,
          fontWeight: FontWeight.w700,
          color: AppTheme.textSecondary,
          letterSpacing: 0.8,
        ),
      ),
    );
  }

  Widget _contactRow({
    required IconData icon,
    required String title,
    required String subtitle,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
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
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: AppTheme.primaryContainer,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: AppTheme.primary, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: GoogleFonts.manrope(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                  ),
                ),
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
        ],
      ),
    );
  }
}

class _Faq {
  final String question;
  final String answer;
  const _Faq(this.question, this.answer);
}

class _FaqTile extends StatelessWidget {
  final _Faq faq;
  const _FaqTile({required this.faq});

  @override
  Widget build(BuildContext context) {
    return Theme(
      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        childrenPadding:
            const EdgeInsets.fromLTRB(16, 0, 16, 14),
        iconColor: AppTheme.primary,
        collapsedIconColor: AppTheme.iconLight,
        title: Text(
          faq.question,
          style: GoogleFonts.manrope(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            color: AppTheme.textPrimary,
          ),
        ),
        children: [
          Align(
            alignment: Alignment.centerLeft,
            child: Text(
              faq.answer,
              style: GoogleFonts.manrope(
                fontSize: 13,
                color: AppTheme.textSecondary,
                height: 1.5,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
