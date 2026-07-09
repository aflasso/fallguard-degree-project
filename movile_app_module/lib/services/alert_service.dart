import 'dart:async';
import 'dart:convert';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:http/http.dart' as http;

import '../models/alert_model.dart';

class AlertService {
  AlertService._();

  static String get _baseUrl =>
      kIsWeb ? 'http://localhost:8000' : 'http://10.0.2.2:8000';

  static final _db = FirebaseFirestore.instance;

  static String get _uid => FirebaseAuth.instance.currentUser!.uid;

  static DocumentReference<Map<String, dynamic>> get _userRef =>
      _db.collection('users').doc(_uid);

  // ── Helpers ────────────────────────────────────────────────────────────────

  static Future<String> _token() async =>
      await FirebaseAuth.instance.currentUser!.getIdToken() ?? '';

  static Future<Map<String, String>> _headers() async => {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ${await _token()}',
      };

  // ── Perfil de usuario ──────────────────────────────────────────────────────

  static Future<void> createUserProfile({
    required String name,
    required String email,
    required String cameraId,
  }) async {
    final fcmToken = await FirebaseMessaging.instance.getToken(
      vapidKey:
          'BNFVSCdyTc2wCy7QPyioXdJyDKdpDi-sO7fFj_ijtmu03GDEUY9zFWjKCDp146wVeYTb4PYVCQ0WUecZHxOpnnY',
    );
    final res = await http.post(
      Uri.parse('$_baseUrl/api/users'),
      headers: await _headers(),
      body: jsonEncode({
        'user_id': _uid,
        'name': name,
        'email': email,
        'fcm_token': fcmToken ?? '',
        'cameraId': cameraId,
        'cameraLocation':
            cameraId.isNotEmpty ? 'Cámara · $cameraId' : 'Sin ubicación',
      }),
    );
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception(
          'createUserProfile failed: ${res.statusCode} ${res.body}');
    }
  }

  static Future<void> linkModule(String moduleId) async {
    final res = await http.post(
      Uri.parse('$_baseUrl/api/modules/link'),
      headers: await _headers(),
      body: jsonEncode({'module_id': moduleId, 'user_id': _uid}),
    );
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception('linkModule failed: ${res.statusCode} ${res.body}');
    }
  }

  static Future<void> unlinkModule(String moduleId) async {
    final res = await http.post(
      Uri.parse('$_baseUrl/api/modules/unlink'),
      headers: await _headers(),
      body: jsonEncode({'module_id': moduleId, 'user_id': _uid}),
    );
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception('unlinkModule failed: ${res.statusCode} ${res.body}');
    }
  }

  static Future<void> renameModule(String moduleId, String displayName) async {
    final res = await http.patch(
      Uri.parse('$_baseUrl/api/modules/$moduleId/name'),
      headers: await _headers(),
      body: jsonEncode({'display_name': displayName}),
    );
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception('renameModule failed: ${res.statusCode} ${res.body}');
    }
  }

  /// Configura la fuente de video del módulo. El servidor valida el esquema de
  /// la URL y devuelve el motivo del rechazo en `detail`; se propaga tal cual
  /// porque está redactado para mostrárselo al usuario.
  static Future<void> setModuleCamera(String moduleId, String url) async {
    final res = await http.patch(
      Uri.parse('$_baseUrl/api/modules/$moduleId/camera'),
      headers: await _headers(),
      body: jsonEncode({'url': url}),
    );
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception(_detail(res.body) ?? 'No se pudo guardar la cámara');
    }
  }

  /// Extrae el campo `detail` de un error de FastAPI.
  static String? _detail(String body) {
    try {
      final decoded = jsonDecode(body);
      if (decoded is Map && decoded['detail'] is String) {
        return decoded['detail'] as String;
      }
    } catch (_) {
      // Cuerpo no-JSON: caemos al mensaje genérico del llamador.
    }
    return null;
  }

  static Future<void> updateFcmToken(String token) async {
    final res = await http.patch(
      Uri.parse('$_baseUrl/api/users/$_uid/fcm-token'),
      headers: await _headers(),
      body: jsonEncode({'fcm_token': token}),
    );
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception('updateFcmToken failed: ${res.statusCode} ${res.body}');
    }
  }

  static Stream<Map<String, dynamic>?> userProfileStream() {
    return _userRef.snapshots().map((doc) => doc.data());
  }

  static Stream<List<Map<String, dynamic>>> linkedModulesStream() {
    return _db
        .collection('modules')
        .where('user_id', isEqualTo: _uid)
        .snapshots()
        .map((snap) => snap.docs.map((d) => d.data()).toList());
  }

  /// True si el módulo está conectado pero su cámara dejó de entregar frames:
  /// sigue online y no detecta nada.
  ///
  /// Solo aplica a módulos conectados — en uno desconectado `camera_ok` es el
  /// último valor reportado y no dice nada del presente. Los documentos previos
  /// a este campo no lo traen y se asumen sanos.
  static bool isCameraDown(Map<String, dynamic> module) {
    final connected = (module['status'] as String?) == 'connected';
    final cameraOk = (module['camera_ok'] as bool?) ?? true;
    return connected && !cameraOk;
  }

  // ── Alertas ────────────────────────────────────────────────────────────────

  /// Alertas del usuario en tiempo real desde Firestore (igual que los módulos).
  /// Antes se sondeaba por REST cada 30s, lo que retrasaba la actualización del
  /// estado en la pantalla principal; ahora refleja los cambios al instante.
  static Stream<List<AlertModel>> alertsStream() {
    return _db
        .collection('alerts')
        .where('user_id', isEqualTo: _uid)
        .snapshots()
        .map((snap) {
      final list = snap.docs.map((d) {
        final m = d.data();
        return AlertModel(
          id: m['alert_id'] as String? ?? d.id,
          timestamp: _parseTimestamp(m['timestamp']),
          status: AlertStatus.values.firstWhere(
            (e) => e.name == (m['status'] as String? ?? 'detected'),
            orElse: () => AlertStatus.detected,
          ),
          location: m['location'] as String? ?? '',
          elderlyName: m['elderlyName'] as String? ?? '',
          description: m['description'] as String? ?? '',
        );
      }).toList();
      // Orden descendente por fecha (más reciente primero), como hacía el REST.
      list.sort((a, b) => b.timestamp.compareTo(a.timestamp));
      return list;
    });
  }

  static DateTime _parseTimestamp(dynamic raw) {
    if (raw is Timestamp) return raw.toDate();
    if (raw is String) return DateTime.tryParse(raw) ?? DateTime.now();
    return DateTime.now();
  }

  static Future<void> updateAlertStatus(
      String alertId, AlertStatus status) async {
    final res = await http.patch(
      Uri.parse('$_baseUrl/api/alerts/$alertId/seen'),
      headers: await _headers(),
      body: jsonEncode({'status': status.name}),
    );
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception(
          'updateAlertStatus failed: ${res.statusCode} ${res.body}');
    }  }

  static Stream<AlertModel?> latestAlertStream() =>
      alertsStream().map((list) => list.isEmpty ? null : list.first);

  static Future<String> getClipReadUrl(String alertId) async {
    final res = await http.get(
      Uri.parse('$_baseUrl/api/clips/read-url?alert_id=$alertId'),
      headers: await _headers(),
    );
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception('getClipReadUrl failed: ${res.statusCode} ${res.body}');
    }
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    return data['read_url'] as String;
  }

  static Future<void> deleteAlert(String alertId) async {
    final res = await http.delete(
      Uri.parse('$_baseUrl/api/alerts/$alertId'),
      headers: await _headers(),
    );
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception('deleteAlert failed: ${res.statusCode} ${res.body}');
    }  }

  static Future<void> deleteAllAlerts() async {
    final res = await http.delete(
      Uri.parse('$_baseUrl/api/alerts?user_id=$_uid'),
      headers: await _headers(),
    );
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception('deleteAllAlerts failed: ${res.statusCode} ${res.body}');
    }  }
}
