import 'package:cloud_firestore/cloud_firestore.dart';

enum AlertStatus { confirmed, dismissed, falseAlarm, pending }

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

  factory AlertModel.fromFirestore(
      DocumentSnapshot<Map<String, dynamic>> doc) {
    final data = doc.data()!;
    return AlertModel(
      id: doc.id,
      timestamp: (data['timestamp'] as Timestamp).toDate(),
      status: AlertStatus.values.firstWhere(
        (e) => e.name == (data['status'] as String? ?? 'pending'),
        orElse: () => AlertStatus.pending,
      ),
      location: data['location'] as String? ?? '',
      elderlyName: data['elderlyName'] as String? ?? '',
      description: data['description'] as String? ?? '',
    );
  }

  Map<String, dynamic> toFirestore() => {
        'timestamp': Timestamp.fromDate(timestamp),
        'status': status.name,
        'location': location,
        'elderlyName': elderlyName,
        'description': description,
      };

  String get statusLabel {
    switch (status) {
      case AlertStatus.confirmed:
        return 'CONFIRMADA';
      case AlertStatus.dismissed:
        return 'DESCARTADA';
      case AlertStatus.falseAlarm:
        return 'FALSA ALARMA';
      case AlertStatus.pending:
        return 'PENDIENTE';
    }
  }
}
