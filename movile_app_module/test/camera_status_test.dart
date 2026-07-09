import 'package:flutter_test/flutter_test.dart';
import 'package:fallguard/services/alert_service.dart';

void main() {
  group('AlertService.isCameraDown', () {
    test('modulo conectado con camara caida', () {
      expect(
        AlertService.isCameraDown({'status': 'connected', 'camera_ok': false}),
        isTrue,
      );
    });

    test('modulo conectado y sano', () {
      expect(
        AlertService.isCameraDown({'status': 'connected', 'camera_ok': true}),
        isFalse,
      );
    });

    test('modulo desconectado: camera_ok es un valor viejo, no dice nada del presente', () {
      expect(
        AlertService.isCameraDown({'status': 'disconnected', 'camera_ok': false}),
        isFalse,
      );
    });

    test('doc legado sin camera_ok se asume sano', () {
      expect(
        AlertService.isCameraDown({'status': 'connected'}),
        isFalse,
      );
    });

    test('doc sin status no revienta', () {
      expect(AlertService.isCameraDown({}), isFalse);
    });
  });
}
