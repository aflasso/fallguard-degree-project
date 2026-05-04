import '../models/alert_model.dart';

class MockService {
  MockService._();

  static final List<AlertModel> alerts = [
    AlertModel(
      id: '1',
      timestamp: DateTime(2023, 10, 12, 9, 15),
      status: AlertStatus.confirmed,
      location: 'Sala de Estar',
      elderlyName: 'Abuela Maria',
      description:
          'Se detectó un impacto significativo. Por favor, verifique el estado del usuario de inmediato.',
    ),
    AlertModel(
      id: '2',
      timestamp: DateTime(2023, 10, 10, 14, 42),
      status: AlertStatus.confirmed,
      location: 'Dormitorio',
      elderlyName: 'Abuela Maria',
      description:
          'Se detectó un impacto significativo. Por favor, verifique el estado del usuario de inmediato.',
    ),
    AlertModel(
      id: '3',
      timestamp: DateTime(2023, 10, 5, 23, 8),
      status: AlertStatus.confirmed,
      location: 'Sala de Estar',
      elderlyName: 'Abuela Maria',
      description:
          'Se detectó un impacto significativo. Por favor, verifique el estado del usuario de inmediato.',
    ),
    AlertModel(
      id: '4',
      timestamp: DateTime(2023, 9, 28, 11, 20),
      status: AlertStatus.confirmed,
      location: 'Cocina',
      elderlyName: 'Abuela Maria',
      description:
          'Se detectó un impacto significativo. Por favor, verifique el estado del usuario de inmediato.',
    ),
    AlertModel(
      id: '5',
      timestamp: DateTime(2023, 9, 15, 3, 45),
      status: AlertStatus.confirmed,
      location: 'Baño',
      elderlyName: 'Abuela Maria',
      description:
          'Se detectó un impacto significativo. Por favor, verifique el estado del usuario de inmediato.',
    ),
  ];

  static const Map<String, dynamic> currentUser = {
    'name': 'Elena Caregiver',
    'email': 'elena.caregiver@fallguard.app',
    'elderlyName': 'Abuela Maria',
    'cameraLocation': 'Casa - Sala de Estar',
    'isMonitoring': true,
  };

  static Future<bool> login(String email, String password) async {
    await Future.delayed(const Duration(milliseconds: 800));
    return email.isNotEmpty && password.isNotEmpty;
  }

  static Future<bool> register({
    required String name,
    required String email,
    required String password,
    required String cameraId,
  }) async {
    await Future.delayed(const Duration(milliseconds: 1200));
    return true;
  }
}
