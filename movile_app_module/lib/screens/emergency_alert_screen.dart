import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../models/alert_model.dart';
import '../services/alert_service.dart';
import '../theme/app_theme.dart';

class EmergencyAlertScreen extends StatefulWidget {
  const EmergencyAlertScreen({super.key});

  @override
  State<EmergencyAlertScreen> createState() => _EmergencyAlertScreenState();
}

class _EmergencyAlertScreenState extends State<EmergencyAlertScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulseController;
  late final Animation<double> _pulseAnimation;

  // Datos de la alerta recibidos como argumentos de ruta
  String? _alertId;
  String _location = 'Ubicación desconocida';
  String _elderlyName = 'Paciente';
  late final DateTime _openTime;
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _openTime = DateTime.now();
    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 900),
      vsync: this,
    )..repeat(reverse: true);
    _pulseAnimation = Tween<double>(begin: 0.92, end: 1.08).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Leer argumentos solo la primera vez
    if (_alertId == null) {
      final args =
          ModalRoute.of(context)?.settings.arguments as Map<String, dynamic>?;
      if (args != null) {
        _alertId = args['alertId'] as String?;
        final location = args['location'] as String? ?? '';
        final elderlyName = args['elderlyName'] as String? ?? '';
        if (location.isNotEmpty) _location = location;
        if (elderlyName.isNotEmpty) _elderlyName = elderlyName;
      }
    }
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  String get _formattedTime {
    final h = _openTime.hour.toString().padLeft(2, '0');
    final m = _openTime.minute.toString().padLeft(2, '0');
    return '$h:$m';
  }

  Future<void> _confirm() async {
    setState(() => _isLoading = true);
    if (_alertId != null) {
      await AlertService.updateAlertStatus(_alertId!, AlertStatus.confirmed);
    }
    if (mounted) Navigator.pop(context);
  }

  Future<void> _falseAlarm() async {
    setState(() => _isLoading = true);
    if (_alertId != null) {
      await AlertService.updateAlertStatus(_alertId!, AlertStatus.falseAlarm);
    }
    if (mounted) Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Color(0xFF8B0000),
              Color(0xFF6B0000),
              Color(0xFF3D0000),
            ],
          ),
        ),
        child: SafeArea(
          child: Stack(
            children: [
              // Faded house background
              Positioned(
                bottom: 0,
                left: 0,
                right: 0,
                height: 220,
                child: Opacity(
                  opacity: 0.12,
                  child: CustomPaint(painter: _HousePainter()),
                ),
              ),

              // Main content
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: Column(
                  children: [
                    // ── Top bar ────────────────────────────────────
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.shield,
                                  color: Colors.white, size: 20),
                              const SizedBox(width: 6),
                              Text(
                                'FallGuard',
                                style: GoogleFonts.manrope(
                                  fontSize: 16,
                                  fontWeight: FontWeight.w700,
                                  color: Colors.white,
                                ),
                              ),
                            ],
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 12, vertical: 5),
                            decoration: BoxDecoration(
                              color: const Color(0xFFB71C1C),
                              borderRadius: BorderRadius.circular(20),
                            ),
                            child: Text(
                              'URGENTE',
                              style: GoogleFonts.manrope(
                                fontSize: 11,
                                fontWeight: FontWeight.w800,
                                color: Colors.white,
                                letterSpacing: 1.2,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 20),

                    // ── Pulsing Warning Icon ───────────────────────
                    AnimatedBuilder(
                      animation: _pulseAnimation,
                      builder: (context, child) => Transform.scale(
                        scale: _pulseAnimation.value,
                        child: child,
                      ),
                      child: Container(
                        width: 96,
                        height: 96,
                        decoration: BoxDecoration(
                          color: const Color(0xFFB71C1C),
                          shape: BoxShape.circle,
                          boxShadow: [
                            BoxShadow(
                              color: Colors.red.withValues(alpha: 0.5),
                              blurRadius: 32,
                              spreadRadius: 12,
                            ),
                          ],
                        ),
                        child: const Icon(
                          Icons.warning_rounded,
                          color: Colors.white,
                          size: 48,
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),

                    // ── Time ──────────────────────────────────────
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Container(
                          width: 7,
                          height: 7,
                          decoration: const BoxDecoration(
                            color: Colors.orange,
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(width: 6),
                        Text(
                          _formattedTime,
                          style: GoogleFonts.manrope(
                            fontSize: 15,
                            fontWeight: FontWeight.w500,
                            color: Colors.white70,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),

                    // ── Main Message ──────────────────────────────
                    Text(
                      'Se detectó una\nposible caída',
                      textAlign: TextAlign.center,
                      style: GoogleFonts.manrope(
                        fontSize: 30,
                        fontWeight: FontWeight.w800,
                        color: Colors.white,
                        height: 1.2,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      'El sensor ha registrado un impacto inusual.\nVerifica el estado del paciente de inmediato.',
                      textAlign: TextAlign.center,
                      style: GoogleFonts.manrope(
                        fontSize: 14,
                        color: Colors.white60,
                        height: 1.5,
                      ),
                    ),
                    const SizedBox(height: 28),

                    // ── Info Chips ────────────────────────────────
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        _infoChip('USUARIO', _elderlyName),
                        const SizedBox(width: 12),
                        _infoChip('UBICACIÓN', _location),
                      ],
                    ),
                    const SizedBox(height: 32),

                    // ── Confirm Button ────────────────────────────
                    SizedBox(
                      width: double.infinity,
                      height: 54,
                      child: ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.white,
                          foregroundColor: AppTheme.alertRed,
                          elevation: 0,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(30),
                          ),
                        ),
                        onPressed: _isLoading ? null : _confirm,
                        child: _isLoading
                            ? const SizedBox(
                                width: 22,
                                height: 22,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: AppTheme.alertRed,
                                ),
                              )
                            : Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  const Icon(Icons.check_circle_outline,
                                      color: AppTheme.alertRed, size: 18),
                                  const SizedBox(width: 8),
                                  Text(
                                    'Confirmar caída',
                                    style: GoogleFonts.manrope(
                                      fontSize: 16,
                                      fontWeight: FontWeight.w700,
                                      color: AppTheme.alertRed,
                                    ),
                                  ),
                                ],
                              ),
                      ),
                    ),
                    const SizedBox(height: 12),

                    // ── False Alarm Button ────────────────────────
                    SizedBox(
                      width: double.infinity,
                      height: 54,
                      child: OutlinedButton(
                        style: OutlinedButton.styleFrom(
                          side: const BorderSide(
                              color: Colors.white38, width: 1.5),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(30),
                          ),
                          foregroundColor: Colors.white,
                        ),
                        onPressed: _isLoading ? null : _falseAlarm,
                        child: Text(
                          'Falsa alarma',
                          style: GoogleFonts.manrope(
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                            color: Colors.white,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _infoChip(String label, String value) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.white.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: GoogleFonts.manrope(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: Colors.white60,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(height: 3),
          Text(
            value,
            style: GoogleFonts.manrope(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: Colors.white,
            ),
          ),
        ],
      ),
    );
  }
}

class _HousePainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.white
      ..style = PaintingStyle.fill;

    _drawHouse(canvas, paint,
        left: size.width * 0.05,
        top: size.height * 0.25,
        width: size.width * 0.28,
        height: size.height * 0.75);

    _drawHouse(canvas, paint,
        left: size.width * 0.35,
        top: size.height * 0.05,
        width: size.width * 0.3,
        height: size.height * 0.95);

    _drawHouse(canvas, paint,
        left: size.width * 0.7,
        top: size.height * 0.35,
        width: size.width * 0.28,
        height: size.height * 0.65);
  }

  void _drawHouse(Canvas canvas, Paint paint,
      {required double left,
      required double top,
      required double width,
      required double height}) {
    final path = Path();
    path.moveTo(left, top + height * 0.35);
    path.lineTo(left + width / 2, top);
    path.lineTo(left + width, top + height * 0.35);
    path.lineTo(left + width, top + height);
    path.lineTo(left, top + height);
    path.close();
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
