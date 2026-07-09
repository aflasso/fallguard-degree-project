import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:http/http.dart' as http;

import '../theme/app_theme.dart';

/// Extrae los JPEG de un stream MJPEG, chunk a chunk.
///
/// En vez de parsear el boundary del multipart (que cada servidor formatea a su
/// manera) se buscan los marcadores del propio JPEG: SOI `FF D8` y EOI `FF D9`.
/// Es independiente del formato del multipart y de los headers de cada parte.
///
/// Los chunks de la red no respetan los límites de los frames: un JPEG puede
/// llegar partido en varios, y un chunk puede traer varios JPEG.
class MjpegFrameParser {
  MjpegFrameParser({this.maxBuffer = 8 * 1024 * 1024});

  /// Si el buffer crece más que esto sin un JPEG completo, la respuesta no es
  /// MJPEG (una página HTML de error, por ejemplo). `addChunk` lanza
  /// [StateError] en vez de comer RAM sin límite.
  final int maxBuffer;

  static const _soi = [0xFF, 0xD8]; // start of image
  static const _eoi = [0xFF, 0xD9]; // end of image

  List<int> _buffer = [];

  int get bufferedBytes => _buffer.length;

  /// Devuelve los frames completos que aparecieron con este chunk.
  List<Uint8List> addChunk(List<int> chunk) {
    _buffer.addAll(chunk);
    final frames = <Uint8List>[];

    while (true) {
      final start = _indexOfMarker(_buffer, _soi, 0);
      if (start < 0) {
        // Sin cabecera de JPEG: descartar lo acumulado, salvo el último byte
        // que podría ser la mitad de un marcador partido entre dos chunks.
        if (_buffer.length > 1) _buffer = _buffer.sublist(_buffer.length - 1);
        break;
      }

      final end = _indexOfMarker(_buffer, _eoi, start + 2);
      if (end < 0) {
        if (start > 0) _buffer = _buffer.sublist(start); // descartar preámbulo
        break;
      }

      frames.add(Uint8List.fromList(_buffer.sublist(start, end + 2)));
      _buffer = _buffer.sublist(end + 2);
    }

    if (_buffer.length > maxBuffer) {
      _buffer = [];
      throw StateError('La respuesta no parece un stream MJPEG');
    }
    return frames;
  }

  static int _indexOfMarker(List<int> data, List<int> marker, int from) {
    for (var i = from; i + 1 < data.length; i++) {
      if (data[i] == marker[0] && data[i + 1] == marker[1]) return i;
    }
    return -1;
  }
}

/// Vista previa en vivo de una cámara MJPEG sobre HTTP (ej. la app IP Webcam).
///
/// `video_player` no sirve acá: un stream MJPEG no es un video, es una respuesta
/// HTTP infinita `multipart/x-mixed-replace` con un JPEG completo por parte.
///
/// La app tiene que estar en la misma red que la cámara. Si no lo está, el
/// widget muestra el error en vez de girar para siempre — por eso el watchdog
/// de `firstFrameTimeout`.
class MjpegView extends StatefulWidget {
  const MjpegView({
    super.key,
    required this.url,
    this.firstFrameTimeout = const Duration(seconds: 8),
    this.onLive,
    this.onFailed,
    this.clientFactory = http.Client.new,
  });

  final String url;
  final Duration firstFrameTimeout;

  /// Inyectable para los tests. `TestWidgetsFlutterBinding` intercepta `HttpClient`
  /// y responde 400 sin tocar la red, así que un test no puede ejercitar el
  /// stream real sin pasar su propio cliente.
  final http.Client Function() clientFactory;

  /// Se llama una vez, al recibir el primer frame. Es la única prueba de que
  /// la cámara existe y responde: quien deja guardar una URL debe esperarla.
  final VoidCallback? onLive;

  /// Se llama al primer fallo, con el motivo ya redactado para el usuario.
  final ValueChanged<String>? onFailed;

  /// True si el esquema admite vista previa. RTSP no se puede reproducir sin
  /// una dependencia nativa; se acepta como fuente pero no se previsualiza.
  static bool canPreview(String url) {
    final scheme = Uri.tryParse(url.trim())?.scheme.toLowerCase();
    return scheme == 'http' || scheme == 'https';
  }

  @override
  State<MjpegView> createState() => _MjpegViewState();
}

class _MjpegViewState extends State<MjpegView> {
  /// Un MJPEG sobre HTTP se corta seguido: la app de la cámara cierra la
  /// conexión, el Wi-Fi hipa. Sin reconexión, un microcorte mata la vista previa.
  static const _maxReconnectBackoff = Duration(seconds: 4);

  final _parser = MjpegFrameParser();

  http.Client? _client;
  StreamSubscription<List<int>>? _sub;
  Timer? _watchdog;
  Timer? _retry;

  Uint8List? _frame;
  String? _error;
  bool _reconnecting = false;
  Duration _backoff = const Duration(milliseconds: 500);

  @override
  void initState() {
    super.initState();
    _connect();
  }

  @override
  void dispose() {
    _teardown();
    super.dispose();
  }

  void _teardown() {
    _watchdog?.cancel();
    _retry?.cancel();
    _sub?.cancel();
    _client?.close();
  }

  Future<void> _connect() async {
    // El watchdog solo vigila el primer frame. Una vez que hubo imagen, un corte
    // se maneja reconectando, no fallando.
    if (_frame == null) {
      _watchdog = Timer(widget.firstFrameTimeout, () {
        if (_frame == null) {
          _fail('No llegó ninguna imagen. Verifica que el celular y la cámara '
              'estén en la misma red Wi-Fi y que la app de la cámara esté activa.');
        }
      });
    }

    final client = widget.clientFactory();
    _client = client;

    try {
      final uri = Uri.tryParse(widget.url.trim());
      if (uri == null || !uri.hasAuthority) {
        _fail('URL inválida');
        return;
      }

      final res = await client.send(http.Request('GET', uri));
      if (!mounted) return;
      if (res.statusCode != 200) {
        _fail('La cámara respondió ${res.statusCode}');
        return;
      }

      _sub = res.stream.listen(
        _onChunk,
        onError: (_) => _onStreamEnded('Se perdió la conexión con la cámara'),
        onDone: () =>
            _onStreamEnded('La cámara cerró la conexión sin enviar imágenes'),
        cancelOnError: true,
      );
    } catch (_) {
      _onStreamEnded('No se pudo conectar con la cámara');
    }
  }

  /// El stream terminó. Si nunca hubo imagen es un fallo; si ya la hubo es un
  /// microcorte y se reintenta conservando el último frame en pantalla.
  void _onStreamEnded(String reason) {
    if (!mounted || _error != null) return;

    if (_frame == null) {
      _fail(reason);
      return;
    }

    _sub?.cancel();
    _client?.close();
    setState(() => _reconnecting = true);

    _retry = Timer(_backoff, () {
      if (!mounted) return;
      _backoff = _backoff * 2 > _maxReconnectBackoff
          ? _maxReconnectBackoff
          : _backoff * 2;
      _connect();
    });
  }

  void _onChunk(List<int> chunk) {
    final List<Uint8List> frames;
    try {
      frames = _parser.addChunk(chunk);
    } on StateError catch (e) {
      _fail(e.message);
      return;
    }

    if (frames.isEmpty || !mounted) return;
    final first = _frame == null;
    setState(() {
      _frame = frames.last; // si llegaron varios, mostrar el más reciente
      _error = null;
      _reconnecting = false;
    });
    _backoff = const Duration(milliseconds: 500);   // el corte quedó atrás
    if (first) {
      _watchdog?.cancel();
      widget.onLive?.call();
    }
  }

  void _fail(String message) {
    _teardown();
    if (!mounted || _error != null) return;   // un solo aviso de fallo
    setState(() {
      _error = message;
      _reconnecting = false;
    });
    widget.onFailed?.call(message);
  }

  @override
  Widget build(BuildContext context) {
    return AspectRatio(
      aspectRatio: 4 / 3,
      child: Container(
        decoration: BoxDecoration(
          color: const Color(0xFF101114),
          borderRadius: BorderRadius.circular(12),
        ),
        clipBehavior: Clip.antiAlias,
        child: Stack(
          fit: StackFit.expand,
          children: [
            _buildContent(),
            // El último frame sigue en pantalla mientras se reconecta: avisar
            // que lo que se ve está congelado.
            if (_reconnecting)
              Positioned(
                left: 8,
                top: 8,
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.black54,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    'Reconectando…',
                    style: GoogleFonts.manrope(
                        fontSize: 11, color: Colors.white),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent() {
    if (_error != null) {
      return Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.videocam_off_outlined,
                color: AppTheme.warning, size: 32),
            const SizedBox(height: 10),
            Text(
              _error!,
              textAlign: TextAlign.center,
              style: GoogleFonts.manrope(fontSize: 12, color: Colors.white70),
            ),
          ],
        ),
      );
    }

    if (_frame == null) {
      return const Center(
        child: CircularProgressIndicator(color: Colors.white54, strokeWidth: 2),
      );
    }

    // Sin `width: double.infinity`: dentro de un AlertDialog, el IntrinsicWidth
    // le pregunta a este hijo su ancho natural, y un infinito revienta el layout.
    return Image.memory(
      _frame!,
      gaplessPlayback: true, // sin parpadeo entre frames
      fit: BoxFit.contain,
    );
  }
}
