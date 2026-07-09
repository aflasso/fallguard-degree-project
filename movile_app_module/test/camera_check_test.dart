import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:fallguard/widgets/camera_check.dart';
import 'package:fallguard/widgets/mjpeg_view.dart';

/// Cliente que no llega a conectar. No sirve apuntar a un puerto cerrado:
/// `TestWidgetsFlutterBinding` intercepta `HttpClient` y responde 400 sin salir
/// a la red, así que el test pasaría por el motivo equivocado.
class _ClienteCaido extends http.BaseClient {
  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) =>
      Future.error(const SocketExceptionStub());
}

class SocketExceptionStub implements Exception {
  const SocketExceptionStub();
}

void main() {
  group('cameraSaveDecision — al configurar la cámara (obligatoria)', () {
    CameraSaveDecision d(CameraCheck c) =>
        cameraSaveDecision(c, cameraOptional: false);

    test('no se puede guardar una URL que no se probó', () {
      expect(d(CameraCheck.unchecked).enabled, isFalse);
    });

    test('no se puede guardar mientras está conectando', () {
      expect(d(CameraCheck.checking).enabled, isFalse);
    });

    test('con imagen en vivo se guarda, y no se marca como sin verificar', () {
      expect(d(CameraCheck.live).enabled, isTrue);
      expect(d(CameraCheck.live).unverified, isFalse);
    });

    test('si la prueba falló se permite el escape, marcado como sin verificar', () {
      // El celular puede estar fuera de la LAN aunque la URL sea correcta.
      expect(d(CameraCheck.failed).enabled, isTrue);
      expect(d(CameraCheck.failed).unverified, isTrue);
    });

    test('rtsp no se puede previsualizar: escape explícito', () {
      expect(d(CameraCheck.unsupported).enabled, isTrue);
      expect(d(CameraCheck.unsupported).unverified, isTrue);
    });

    test('el campo vacío no se puede guardar: sin cámara no hay detección', () {
      expect(d(CameraCheck.empty).enabled, isFalse);
    });
  });

  group('cameraSaveDecision — al vincular (cámara opcional)', () {
    test('se puede vincular sin cámara', () {
      expect(
        cameraSaveDecision(CameraCheck.empty, cameraOptional: true).enabled,
        isTrue,
      );
    });

    test('pero si se escribió una URL, hay que probarla', () {
      expect(
        cameraSaveDecision(CameraCheck.unchecked, cameraOptional: true).enabled,
        isFalse,
      );
    });
  });

  group('MjpegView', () {
    testWidgets('avisa el fallo cuando la cámara no responde', (tester) async {
      String? motivo;

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: MjpegView(
            url: 'http://camara/video',
            clientFactory: _ClienteCaido.new,
            onFailed: (m) => motivo = m,
          ),
        ),
      ));
      await tester.pump();

      expect(motivo, isNotNull,
          reason: 'sin onFailed el diálogo dejaría "Guardar" bloqueado para siempre');
      expect(find.textContaining('cámara'), findsOneWidget);
    });

    testWidgets('se puede montar dentro de un AlertDialog', (tester) async {
      // Regresión: AlertDialog mide su contenido con IntrinsicWidth. Un hijo con
      // ancho natural infinito (Image.memory(width: double.infinity)) hace
      // fallar el layout con "'input.isFinite': is not true".
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => ElevatedButton(
              onPressed: () => showDialog<void>(
                context: context,
                builder: (_) => const AlertDialog(
                  content: SizedBox(
                    width: 300,
                    child: SingleChildScrollView(
                      child: MjpegView(
                        url: 'http://127.0.0.1:1/video',
                        firstFrameTimeout: Duration(milliseconds: 200),
                      ),
                    ),
                  ),
                ),
              ),
              child: const Text('abrir'),
            ),
          ),
        ),
      ));

      await tester.tap(find.text('abrir'));
      await tester.pump();                       // spinner
      expect(tester.takeException(), isNull);

      await tester.pump(const Duration(milliseconds: 500));  // estado de error
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });

    testWidgets('una URL inválida falla sin intentar conectar', (tester) async {
      String? motivo;

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: MjpegView(url: 'no-es-una-url', onFailed: (m) => motivo = m),
        ),
      ));
      await tester.pump();
      await tester.pumpAndSettle();

      expect(motivo, 'URL inválida');
    });
  });
}
