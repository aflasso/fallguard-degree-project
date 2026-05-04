import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:google_sign_in/google_sign_in.dart';
import 'alert_service.dart';

class RegisterResult {
  final String? error;
  final String? moduleWarning;

  const RegisterResult({this.error, this.moduleWarning});

  bool get success => error == null;
}

class AuthService {
  static final _auth = FirebaseAuth.instance;
  static final _googleSignIn = GoogleSignIn();

  static Stream<User?> get authStateChanges => _auth.authStateChanges();

  static User? get currentUser => _auth.currentUser;

  // Garantiza que exista el documento del usuario en Firestore.
  // Se llama después de cualquier tipo de login.
  static Future<void> _ensureUserProfile(User user) async {
    await AlertService.createUserProfile(
      name: user.displayName ?? user.email?.split('@').first ?? 'Usuario',
      email: user.email ?? '',
      cameraId: '',
    );
  }

  // Login con email y contraseña.
  // Retorna null si fue exitoso, o un mensaje de error si falló.
  static Future<String?> signInWithEmail(String email, String password) async {
    try {
      final credential = await _auth.signInWithEmailAndPassword(
        email: email.trim(),
        password: password,
      );
      await _ensureUserProfile(credential.user!);
      return null;
    } on FirebaseAuthException catch (e) {
      return _errorMessage(e.code);
    }
  }

  // Registro con email, contraseña y nombre.
  // Operación atómica: si createUserProfile falla, se elimina el usuario de Auth.
  // La vinculación del módulo es opcional: si falla, el registro igual es exitoso.
  static Future<RegisterResult> registerWithEmail({
    required String name,
    required String email,
    required String password,
    required String cameraId,
  }) async {
    User? createdUser;
    try {
      final credential = await _auth.createUserWithEmailAndPassword(
        email: email.trim(),
        password: password,
      );
      createdUser = credential.user!;
      await createdUser.updateDisplayName(name.trim());

      await AlertService.createUserProfile(
        name: name.trim(),
        email: email.trim(),
        cameraId: cameraId,
      );
    } on FirebaseAuthException catch (e) {
      return RegisterResult(error: _errorMessage(e.code));
    } catch (e) {
      await createdUser?.delete();
      return const RegisterResult(error: 'Error al guardar el perfil. Intenta de nuevo.');
    }

    if (cameraId.trim().isEmpty) return const RegisterResult();

    try {
      await AlertService.linkModule(cameraId.trim());
    } catch (_) {
      return const RegisterResult(
        moduleWarning: 'Cuenta creada, pero no se pudo vincular el módulo. Puedes hacerlo desde ajustes.',
      );
    }

    return const RegisterResult();
  }

  // Login con Google OAuth.
  // En web usa signInWithPopup (no requiere configuración extra).
  // En móvil usa el flujo nativo de google_sign_in.
  static Future<String?> signInWithGoogle() async {
    try {
      UserCredential result;

      if (kIsWeb) {
        final provider = GoogleAuthProvider();
        result = await _auth.signInWithPopup(provider);
      } else {
        final googleUser = await _googleSignIn.signIn();
        if (googleUser == null) return 'Inicio de sesión cancelado';

        final googleAuth = await googleUser.authentication;
        final credential = GoogleAuthProvider.credential(
          accessToken: googleAuth.accessToken,
          idToken: googleAuth.idToken,
        );
        result = await _auth.signInWithCredential(credential);
      }

      await _ensureUserProfile(result.user!);
      return null;
    } on FirebaseAuthException catch (e) {
      return _errorMessage(e.code);
    } catch (_) {
      return 'Error al iniciar sesión con Google';
    }
  }

  static Future<void> signOut() async {
    // En web, google_sign_in requiere clientId en index.html — se omite
    if (!kIsWeb) await _googleSignIn.signOut();
    await _auth.signOut();
  }

  static String _errorMessage(String code) {
    switch (code) {
      case 'user-not-found':
        return 'No existe una cuenta con este correo';
      case 'wrong-password':
      case 'invalid-credential':
        return 'Correo o contraseña incorrectos';
      case 'email-already-in-use':
        return 'Ya existe una cuenta con este correo';
      case 'weak-password':
        return 'La contraseña debe tener al menos 6 caracteres';
      case 'invalid-email':
        return 'El correo no es válido';
      case 'too-many-requests':
        return 'Demasiados intentos. Intenta más tarde';
      default:
        return 'Error de autenticación. Intenta de nuevo';
    }
  }
}
