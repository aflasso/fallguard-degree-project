import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:video_player/video_player.dart';
import '../models/alert_model.dart';
import '../services/alert_service.dart';
import '../theme/app_theme.dart';

class EmergencyAlertScreen extends StatefulWidget {
  const EmergencyAlertScreen({super.key});

  @override
  State<EmergencyAlertScreen> createState() => _EmergencyAlertScreenState();
}

class _EmergencyAlertScreenState extends State<EmergencyAlertScreen> {
  String? _alertId;
  DateTime? _timestamp;

  bool _argsLoaded = false;
  bool _isLoading = false;

  // Web: URL presignada para abrir en el navegador
  String? _webReadUrl;

  // Mobile: controlador de video
  VideoPlayerController? _videoController;
  bool _videoReady = false;
  String? _videoError;

  static const List<String> _months = [
    'ene', 'feb', 'mar', 'abr', 'may', 'jun',
    'jul', 'ago', 'sep', 'oct', 'nov', 'dic',
  ];

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_argsLoaded) {
      _argsLoaded = true;
      final args =
          ModalRoute.of(context)?.settings.arguments as Map<String, dynamic>?;
      if (args != null) {
        _alertId = args['alertId'] as String?;
        final ts = args['timestamp'] as String?;
        if (ts != null && ts.isNotEmpty) _timestamp = DateTime.tryParse(ts);
      }
      _initVideo();
    }
  }

  void _initVideo() {
    if (_alertId == null) return;
    AlertService.getClipReadUrl(_alertId!).then((readUrl) {
      if (!mounted) return;
      if (kIsWeb) {
        setState(() => _webReadUrl = readUrl);
        return;
      }
      final controller = VideoPlayerController.networkUrl(Uri.parse(readUrl));
      _videoController = controller;
      controller.initialize().then((_) {
        if (!mounted) return;
        setState(() => _videoReady = true);
        controller.play();
        controller.setLooping(true);
      }).catchError((e) {
        if (mounted) setState(() => _videoError = 'Error al cargar el video: $e');
      });
    }).catchError((e) {
      if (mounted) setState(() => _videoError = 'Error al obtener URL del clip: $e');
    });
  }

  @override
  void dispose() {
    _videoController?.dispose();
    super.dispose();
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

  void _togglePlayPause() {
    final ctrl = _videoController;
    if (ctrl == null) return;
    setState(() {
      ctrl.value.isPlaying ? ctrl.pause() : ctrl.play();
    });
  }

  String _formatTimestamp(DateTime dt) {
    final h = dt.hour.toString().padLeft(2, '0');
    final m = dt.minute.toString().padLeft(2, '0');
    return '${dt.day} ${_months[dt.month - 1]} ${dt.year} · $h:$m';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new, size: 18),
          color: AppTheme.textPrimary,
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(
          'Caída detectada',
          style: GoogleFonts.manrope(
            fontSize: 17,
            fontWeight: FontWeight.w700,
            color: AppTheme.textPrimary,
          ),
        ),
      ),
      body: Column(
        children: [
          // ── Scrollable content ───────────────────────────────────────
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // ── Video ──────────────────────────────────────────
                  ClipRRect(
                    borderRadius: BorderRadius.circular(16),
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxHeight: 240),
                      child: AspectRatio(
                        aspectRatio: 16 / 9,
                        child: _buildVideoArea(),
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),

                  // ── Info card ──────────────────────────────────────
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppTheme.surface,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: AppTheme.divider),
                    ),
                    child: Row(
                      children: [
                        Container(
                          width: 40,
                          height: 40,
                          decoration: BoxDecoration(
                            color: AppTheme.alertRedLight,
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: const Icon(
                            Icons.warning_amber_rounded,
                            color: AppTheme.alertRed,
                            size: 20,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Posible caída detectada',
                                style: GoogleFonts.manrope(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w700,
                                  color: AppTheme.textPrimary,
                                ),
                              ),
                              if (_timestamp != null) ...[
                                const SizedBox(height: 2),
                                Text(
                                  _formatTimestamp(_timestamp!),
                                  style: GoogleFonts.manrope(
                                    fontSize: 12,
                                    color: AppTheme.textSecondary,
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Revisa el clip y confirma si fue una caída real o una falsa alarma.',
                    style: GoogleFonts.manrope(
                      fontSize: 13,
                      color: AppTheme.textSecondary,
                      height: 1.5,
                    ),
                  ),
                  const SizedBox(height: 16),
                ],
              ),
            ),
          ),

          // ── Buttons — fixed at bottom ────────────────────────────────
          Container(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
            decoration: const BoxDecoration(
              color: AppTheme.background,
              border: Border(top: BorderSide(color: AppTheme.divider)),
            ),
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      SizedBox(
                        height: 52,
                        width: double.infinity,
                        child: ElevatedButton.icon(
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppTheme.alertRed,
                            foregroundColor: Colors.white,
                            minimumSize: Size.zero,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(30),
                            ),
                          ),
                          icon: const Icon(Icons.check_circle_outline, size: 18),
                          label: Text(
                            'Confirmar caída',
                            style: GoogleFonts.manrope(
                              fontSize: 15,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          onPressed: _confirm,
                        ),
                      ),
                      const SizedBox(height: 10),
                      SizedBox(
                        height: 52,
                        width: double.infinity,
                        child: OutlinedButton.icon(
                          style: OutlinedButton.styleFrom(
                            minimumSize: Size.zero,
                            side: const BorderSide(
                                color: AppTheme.divider, width: 1.5),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(30),
                            ),
                          ),
                          icon: const Icon(Icons.cancel_outlined,
                              size: 18, color: AppTheme.textSecondary),
                          label: Text(
                            'Falsa alarma',
                            style: GoogleFonts.manrope(
                              fontSize: 15,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.textSecondary,
                            ),
                          ),
                          onPressed: _falseAlarm,
                        ),
                      ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildVideoArea() {
    if (_videoError != null) {
      return _videoPlaceholder(Icons.error_outline, _videoError!);
    }

    // ── Web: mostrar botón para abrir en pestaña nueva ────────────────────
    if (kIsWeb) {
      if (_webReadUrl == null) {
        return Container(
          color: Colors.black,
          child: const Center(
            child: CircularProgressIndicator(color: Colors.white70),
          ),
        );
      }
      return Container(
        color: const Color(0xFF1A1A1A),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.videocam_outlined, color: Colors.white54, size: 40),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.white12,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(20),
                ),
              ),
              icon: const Icon(Icons.open_in_new, size: 16),
              label: Text(
                'Abrir clip en el navegador',
                style: GoogleFonts.manrope(fontSize: 13),
              ),
              onPressed: () => launchUrl(
                Uri.parse(_webReadUrl!),
                mode: LaunchMode.externalApplication,
              ),
            ),
          ],
        ),
      );
    }

    // ── Mobile: video_player ──────────────────────────────────────────────
    if (!_videoReady) {
      return Container(
        color: Colors.black,
        child: const Center(
          child: CircularProgressIndicator(color: Colors.white70),
        ),
      );
    }
    return GestureDetector(
      onTap: _togglePlayPause,
      child: Stack(
        alignment: Alignment.center,
        children: [
          VideoPlayer(_videoController!),
          ValueListenableBuilder<VideoPlayerValue>(
            valueListenable: _videoController!,
            builder: (_, value, __) {
              return AnimatedOpacity(
                opacity: value.isPlaying ? 0.0 : 1.0,
                duration: const Duration(milliseconds: 200),
                child: Container(
                  decoration: const BoxDecoration(
                    color: Colors.black45,
                    shape: BoxShape.circle,
                  ),
                  padding: const EdgeInsets.all(14),
                  child: const Icon(Icons.play_arrow,
                      color: Colors.white, size: 36),
                ),
              );
            },
          ),
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            child: VideoProgressIndicator(
              _videoController!,
              allowScrubbing: true,
              padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 8),
              colors: const VideoProgressColors(
                playedColor: Colors.white,
                backgroundColor: Colors.white24,
                bufferedColor: Colors.white38,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _videoPlaceholder(IconData icon, String message) {
    return Container(
      color: const Color(0xFF1A1A1A),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, color: Colors.white38, size: 40),
          const SizedBox(height: 8),
          Text(
            message,
            style: GoogleFonts.manrope(color: Colors.white38, fontSize: 13),
          ),
        ],
      ),
    );
  }
}
