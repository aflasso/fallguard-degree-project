// ignore: avoid_web_libraries_in_flutter
import 'dart:html' as html show BroadcastChannel;

void listenFcmBroadcastChannel(void Function(Map<String, dynamic>) onData) {
  html.BroadcastChannel('fcm_fallguard').onMessage.listen((event) {
    onData(Map<String, dynamic>.from(event.data as Map));
  });
}
