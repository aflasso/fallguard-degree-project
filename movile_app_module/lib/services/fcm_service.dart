// ignore: avoid_web_libraries_in_flutter
import 'dart:html' as html show BroadcastChannel;

import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart' show kDebugMode, kIsWeb;
import '../navigation_key.dart';
import 'alert_service.dart';

class FcmService {
  FcmService._();

  static const _vapidKey =
      'BNFVSCdyTc2wCy7QPyioXdJyDKdpDi-sO7fFj_ijtmu03GDEUY9zFWjKCDp146wVeYTb4PYVCQ0WUecZHxOpnnY';

  static Future<void> initialize() async {
    if (kIsWeb) {
      // En web el SW envía el mensaje vía BroadcastChannel
      html.BroadcastChannel('fcm_fallguard').onMessage.listen((event) {
        final data = Map<String, dynamic>.from(event.data as Map);
        if (kDebugMode) print('[FCM] BroadcastChannel: $data');
        if (data['type'] == 'fall_detected') _goToEmergencyFromData(data);
      });
    } else {
      // En móvil usar FirebaseMessaging normalmente
      FirebaseMessaging.onMessage.listen((message) {
        if (kDebugMode) print('[FCM] onMessage: ${message.data}');
        if (_isFallAlert(message)) _goToEmergency(message);
      });
    }

    FirebaseMessaging.onMessageOpenedApp.listen((message) {
      if (kDebugMode) print('[FCM] onMessageOpenedApp: ${message.data}');
      if (_isFallAlert(message)) _goToEmergency(message);
    });

    try {
      final settings = await FirebaseMessaging.instance.requestPermission(
        alert: true,
        badge: true,
        sound: true,
      );
      if (kDebugMode) print('[FCM] Permiso: ${settings.authorizationStatus}');

      await _saveToken();
      if (!kIsWeb) FirebaseMessaging.instance.onTokenRefresh.listen(_persistToken);

      final initial = await FirebaseMessaging.instance.getInitialMessage();
      if (initial != null && _isFallAlert(initial)) _goToEmergency(initial);
    } catch (e) {
      if (kDebugMode) print('[FCM] Error en initialize: $e');
    }
  }

  // ── Helpers ─────────────────────────────────────────────────────────────

  static bool _isFallAlert(RemoteMessage message) =>
      message.data['type'] == 'fall_detected';

  static void _goToEmergency(RemoteMessage message) {
    _goToEmergencyFromData(message.data);
  }

  static void _goToEmergencyFromData(Map<String, dynamic> data) {
    navigatorKey.currentState?.pushNamed(
      '/emergency',
      arguments: {
        'alertId':   data['alert_id'],
        'clipUrl':   data['clip_url'] ?? '',
        'timestamp': data['timestamp'] ?? '',
      },
    );
  }

  static Future<void> _saveToken() async {
    final token = await FirebaseMessaging.instance.getToken(
      vapidKey: kIsWeb ? _vapidKey : null,
    );
    if (kDebugMode) print('[FCM] Token: $token');
    if (token != null) await _persistToken(token);
  }

  static Future<void> _persistToken(String token) async {
    if (FirebaseAuth.instance.currentUser == null) return;
    await AlertService.updateFcmToken(token);
  }
}
