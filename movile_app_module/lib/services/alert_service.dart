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

  // ── Alertas ────────────────────────────────────────────────────────────────

  static Future<List<AlertModel>> _fetchAlerts() async {
    final res = await http.get(
      Uri.parse('$_baseUrl/api/alerts?user_id=$_uid'),
      headers: await _headers(),
    );
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception('fetchAlerts failed: ${res.statusCode} ${res.body}');
    }
    final List<dynamic> raw = jsonDecode(res.body) as List<dynamic>;
    return raw.map((json) {
      final m = json as Map<String, dynamic>;
      return AlertModel(
        id: m['id'] as String,
        timestamp: DateTime.parse(m['timestamp'] as String),
        status: AlertStatus.values.firstWhere(
          (e) => e.name == (m['status'] as String? ?? 'pending'),
          orElse: () => AlertStatus.pending,
        ),
        location: m['location'] as String? ?? '',
        elderlyName: m['elderlyName'] as String? ?? '',
        description: m['description'] as String? ?? '',
      );
    }).toList();
  }

  static Stream<List<AlertModel>> alertsStream() async* {
    while (true) {
      yield await _fetchAlerts();
      await Future.delayed(const Duration(seconds: 30));
    }
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
    }
  }

  static Stream<AlertModel?> latestAlertStream() =>
      alertsStream().map((list) => list.isEmpty ? null : list.first);
}
