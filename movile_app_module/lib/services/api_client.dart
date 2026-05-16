import 'dart:convert';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:http/http.dart' as http;

class ApiClient {
  ApiClient._();

  static String get baseUrl =>
      kIsWeb ? 'http://localhost:8000' : 'http://10.0.2.2:8000';

  static Future<Map<String, String>> authHeaders() async {
    final token =
        await FirebaseAuth.instance.currentUser?.getIdToken() ?? '';
    return {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer $token',
    };
  }

  static Future<http.Response> postJson(
    String path, {
    Map<String, dynamic>? body,
    bool requireAuth = true,
  }) async {
    final headers = requireAuth
        ? await authHeaders()
        : <String, String>{'Content-Type': 'application/json'};
    return http.post(
      Uri.parse('$baseUrl$path'),
      headers: headers,
      body: body == null ? null : jsonEncode(body),
    );
  }

  static String extractError(http.Response res, String fallback) {
    try {
      final data = jsonDecode(res.body) as Map<String, dynamic>;
      final detail = data['detail'];
      if (detail is String) return detail;
    } catch (_) {}
    return fallback;
  }
}
