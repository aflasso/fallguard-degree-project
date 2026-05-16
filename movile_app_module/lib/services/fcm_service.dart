import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart' show kDebugMode, kIsWeb;
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import '../navigation_key.dart';
import 'alert_service.dart';
import 'fcm_web_channel_stub.dart'
    if (dart.library.html) 'fcm_web_channel_web.dart';

class FcmService {
  FcmService._();

  static const _vapidKey =
      'BNFVSCdyTc2wCy7QPyioXdJyDKdpDi-sO7fFj_ijtmu03GDEUY9zFWjKCDp146wVeYTb4PYVCQ0WUecZHxOpnnY';

  static const _channelId   = 'fall_alerts';
  static const _channelName = 'Alertas de caída';

  static final _localNotif = FlutterLocalNotificationsPlugin();

  static Future<void> initialize() async {
    if (!kIsWeb) {
      await _initLocalNotifications();
    }

    if (kIsWeb) {
      listenFcmBroadcastChannel((data) {
        if (kDebugMode) print('[FCM] BroadcastChannel: $data');
        if (data['type'] == 'fall_detected') _goToEmergencyFromData(data);
      });
    } else {
      FirebaseMessaging.onMessage.listen((message) {
        if (kDebugMode) print('[FCM] onMessage: ${message.data}');
        // App en foreground: navegar directamente, sin notificación local
        // para evitar que el tap en el banner duplique la pantalla.
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

  // ── Local notifications (Android canal + foreground display) ─────────────

  static Future<void> _initLocalNotifications() async {
    const androidChannel = AndroidNotificationChannel(
      _channelId,
      _channelName,
      importance: Importance.max,
      enableVibration: true,
      playSound: true,
    );

    await _localNotif
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(androidChannel);

    await _localNotif.initialize(
      const InitializationSettings(
        android: AndroidInitializationSettings('@mipmap/ic_launcher'),
      ),
      onDidReceiveNotificationResponse: (details) {
        // Toque en notificación local (foreground) → navegar
        final payload = details.payload;
        if (payload != null) {
          // payload = "alertId|timestamp|clipUrl"
          final parts = payload.split('|');
          _goToEmergencyFromData({
            'alert_id':  parts.isNotEmpty ? parts[0] : '',
            'timestamp': parts.length > 1 ? parts[1] : '',
            'clip_url':  parts.length > 2 ? parts[2] : '',
          });
        }
      },
    );
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
