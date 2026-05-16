enum AlertStatus { detected, confirmed, falseAlarm }

class AlertModel {
  final String id;
  final DateTime timestamp;
  final AlertStatus status;
  final String location;
  final String elderlyName;
  final String description;

  const AlertModel({
    required this.id,
    required this.timestamp,
    required this.status,
    required this.location,
    required this.elderlyName,
    required this.description,
  });

  String get statusLabel {
    switch (status) {
      case AlertStatus.detected:
        return 'SIN CONFIRMAR';
      case AlertStatus.confirmed:
        return 'CONFIRMADA';
      case AlertStatus.falseAlarm:
        return 'FALSA ALARMA';
    }
  }
}
