import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:fallguard/widgets/mjpeg_view.dart';

/// "JPEG" mínimo: al parser solo le importan los marcadores SOI/EOI.
final _jpeg = <int>[0xFF, 0xD8, ...List.filled(16, 0x42), 0xFF, 0xD9];

/// Cliente falso. No se puede usar la red real: `TestWidgetsFlutterBinding`
/// intercepta `HttpClient` y responde 400 sin salir a ningún lado.
class _FakeClient extends http.BaseClient {
  _FakeClient(this.abrirStream, {this.status = 200});

  /// Se invoca en cada conexión. La conexión N-ésima puede comportarse distinto.
  final Stream<List<int>> Function(int intento) abrirStream;
  final int status;

  int conexiones = 0;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async =>
      http.StreamedResponse(abrirStream(conexiones++), status);
}

void main() {
  testWidgets('un corte tras haber visto imagen no invalida la verificación',
      (tester) async {
    // 1ª conexión: un frame y se corta. 2ª: sigue abierta con otro frame.
    late StreamController<List<int>> segunda;
    final client = _FakeClient((intento) {
      if (intento == 0) return Stream.fromIterable([_jpeg]); // emite y cierra
      segunda = StreamController<List<int>>();
      segunda.add(_jpeg);
      return segunda.stream;
    });

    var live = 0;
    String? fallo;

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: MjpegView(
          url: 'http://camara/video',
          clientFactory: () => client,
          onLive: () => live++,
          onFailed: (m) => fallo = m,
        ),
      ),
    ));
    await tester.pump(); // resuelve send() y entrega el primer frame

    expect(live, 1, reason: 'debió avisar imagen en vivo con el primer frame');
    expect(fallo, isNull,
        reason: 'el corte tras ver imagen NO es un fallo: se reconecta');
    expect(find.text('Reconectando…'), findsOneWidget,
        reason: 'el último frame sigue en pantalla, avisando que está congelado');

    // El backoff inicial es 500 ms.
    await tester.pump(const Duration(milliseconds: 600));
    await tester.pump();

    expect(client.conexiones, 2, reason: 'debió reabrir la conexión');
    expect(find.text('Reconectando…'), findsNothing,
        reason: 'con imagen de vuelta, el aviso desaparece');
    expect(fallo, isNull);
    expect(live, 1, reason: 'onLive es de una sola vez');

    await segunda.close();
    tester.takeException(); // Image.memory no decodifica el JPEG falso
  });

  testWidgets('si nunca llegó imagen, el corte sí es un fallo', (tester) async {
    // Conexión que cierra sin enviar ningún frame.
    final client = _FakeClient((_) => const Stream<List<int>>.empty());

    var live = 0;
    String? fallo;

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: MjpegView(
          url: 'http://camara/video',
          clientFactory: () => client,
          onLive: () => live++,
          onFailed: (m) => fallo = m,
        ),
      ),
    ));
    await tester.pump();

    expect(live, 0);
    expect(fallo, isNotNull,
        reason: 'sin imagen no hay nada que verificar: falla, no reconecta');
    expect(client.conexiones, 1, reason: 'no debe reintentar');
  });

  testWidgets('un status distinto de 200 es un fallo inmediato', (tester) async {
    final client = _FakeClient((_) => const Stream<List<int>>.empty(), status: 404);
    String? fallo;

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: MjpegView(
          url: 'http://camara/video',
          clientFactory: () => client,
          onFailed: (m) => fallo = m,
        ),
      ),
    ));
    await tester.pump();

    expect(fallo, contains('404'));
  });
}
