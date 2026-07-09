import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:fallguard/widgets/mjpeg_view.dart';

/// Un "JPEG" mínimo: SOI + carga + EOI. Al parser solo le importan los marcadores.
List<int> jpeg(int fill, {int size = 8}) =>
    [0xFF, 0xD8, ...List.filled(size, fill), 0xFF, 0xD9];

/// Cabecera de parte multipart, como la que manda IP Webcam entre frames.
const boundary = [
  ...[45, 45, 102, 114, 97, 109, 101, 13, 10], // "--frame\r\n"
  ...[13, 10], // \r\n
];

void main() {
  group('MjpegFrameParser', () {
    test('extrae un frame de un chunk completo', () {
      final p = MjpegFrameParser();
      final frames = p.addChunk([...boundary, ...jpeg(0xAA)]);

      expect(frames, hasLength(1));
      expect(frames.first, equals(Uint8List.fromList(jpeg(0xAA))));
      expect(p.bufferedBytes, 0);
    });

    test('reensambla un frame partido entre varios chunks', () {
      // Los chunks de la red no respetan los límites de los frames.
      final p = MjpegFrameParser();
      final full = jpeg(0xBB, size: 12);

      expect(p.addChunk(full.sublist(0, 3)), isEmpty);
      expect(p.addChunk(full.sublist(3, 9)), isEmpty);

      final frames = p.addChunk(full.sublist(9));
      expect(frames, hasLength(1));
      expect(frames.first, equals(Uint8List.fromList(full)));
    });

    test('corta el marcador partido justo entre dos chunks', () {
      // El SOI (FF D8) cae con FF al final de un chunk y D8 al inicio del otro.
      final p = MjpegFrameParser();
      expect(p.addChunk([0x00, 0x00, 0xFF]), isEmpty);

      final frames = p.addChunk([0xD8, 0x01, 0x02, 0xFF, 0xD9]);
      expect(frames, hasLength(1));
      expect(frames.first, equals(Uint8List.fromList([0xFF, 0xD8, 0x01, 0x02, 0xFF, 0xD9])));
    });

    test('extrae varios frames de un solo chunk', () {
      final p = MjpegFrameParser();
      final frames = p.addChunk([
        ...jpeg(0x01),
        ...boundary,
        ...jpeg(0x02),
        ...boundary,
        ...jpeg(0x03),
      ]);

      expect(frames, hasLength(3));
      expect(frames[2], equals(Uint8List.fromList(jpeg(0x03))));
      expect(p.bufferedBytes, 0);
    });

    test('descarta el preámbulo anterior al primer SOI', () {
      final p = MjpegFrameParser();
      final frames = p.addChunk([
        ...'HTTP/1.0 200 OK\r\n\r\n'.codeUnits,
        ...boundary,
        ...jpeg(0x7F),
      ]);
      expect(frames, hasLength(1));
      expect(frames.first.first, 0xFF);
      expect(frames.first[1], 0xD8);
    });

    test('no acumula basura sin marcadores', () {
      // Una respuesta que no es MJPEG no debe hacer crecer el buffer.
      final p = MjpegFrameParser();
      for (var i = 0; i < 50; i++) {
        expect(p.addChunk(List.filled(1000, 0x41)), isEmpty); // 'A'
      }
      expect(p.bufferedBytes, lessThanOrEqualTo(1));
    });

    test('lanza StateError si un JPEG incompleto supera maxBuffer', () {
      // Un SOI seguido de basura infinita: nunca cierra. Debe cortarse.
      final p = MjpegFrameParser(maxBuffer: 4096);
      p.addChunk([0xFF, 0xD8]);
      expect(
        () => p.addChunk(List.filled(5000, 0x41)),
        throwsA(isA<StateError>()),
      );
    });
  });

  group('MjpegView.canPreview', () {
    test('http y https se pueden previsualizar', () {
      expect(MjpegView.canPreview('http://192.168.1.42:8080/video'), isTrue);
      expect(MjpegView.canPreview('https://cam.local/stream'), isTrue);
      expect(MjpegView.canPreview('  http://x/v  '), isTrue);
    });

    test('rtsp se acepta como fuente pero no se previsualiza', () {
      expect(MjpegView.canPreview('rtsp://192.168.1.42:8554/live'), isFalse);
    });

    test('basura no revienta', () {
      expect(MjpegView.canPreview(''), isFalse);
      expect(MjpegView.canPreview('no es una url'), isFalse);
    });
  });
}
