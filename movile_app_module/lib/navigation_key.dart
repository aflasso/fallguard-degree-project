import 'package:flutter/material.dart';

/// Clave global del Navigator. Permite navegar desde fuera del árbol de widgets
/// (ej: handlers de FCM en segundo plano o app terminada).
final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();
