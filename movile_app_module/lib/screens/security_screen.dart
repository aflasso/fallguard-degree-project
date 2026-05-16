import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../theme/app_theme.dart';
import '../services/auth_service.dart';

class SecurityScreen extends StatefulWidget {
  const SecurityScreen({super.key});

  @override
  State<SecurityScreen> createState() => _SecurityScreenState();
}

class _SecurityScreenState extends State<SecurityScreen> {
  final _currentController = TextEditingController();
  final _newController = TextEditingController();
  final _confirmController = TextEditingController();

  bool _obscureCurrent = true;
  bool _obscureNew = true;
  bool _obscureConfirm = true;
  bool _isLoading = false;

  late final bool _canChangePassword;

  @override
  void initState() {
    super.initState();
    _canChangePassword = AuthService.isPasswordProvider();
  }

  @override
  void dispose() {
    _currentController.dispose();
    _newController.dispose();
    _confirmController.dispose();
    super.dispose();
  }

  Future<void> _changePassword() async {
    final current = _currentController.text;
    final next = _newController.text;
    final confirm = _confirmController.text;

    if (current.isEmpty || next.isEmpty) {
      _toast('Completa todos los campos');
      return;
    }
    if (next.length < 6) {
      _toast('La nueva contraseña debe tener al menos 6 caracteres');
      return;
    }
    if (next != confirm) {
      _toast('Las contraseñas no coinciden');
      return;
    }

    setState(() => _isLoading = true);
    final error = await AuthService.updatePassword(
      currentPassword: current,
      newPassword: next,
    );
    if (!mounted) return;
    setState(() => _isLoading = false);

    if (error != null) {
      _toast(error, isError: true);
      return;
    }
    _currentController.clear();
    _newController.clear();
    _confirmController.clear();
    _toast('Contraseña actualizada correctamente');
  }

  Future<void> _sendResetEmail() async {
    setState(() => _isLoading = true);
    final error = await AuthService.sendPasswordResetEmail();
    if (!mounted) return;
    setState(() => _isLoading = false);

    if (error != null) {
      _toast(error, isError: true);
      return;
    }
    _toast(
      'Si el correo existe, recibirás un enlace de restablecimiento. Revisa tu bandeja de entrada y la carpeta de spam.',
    );
  }

  void _toast(String msg, {bool isError = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: isError ? AppTheme.alertRed : null,
        duration: const Duration(seconds: 4),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: AppTheme.background,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: AppTheme.textPrimary),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(
          'Seguridad y Contraseña',
          style: GoogleFonts.manrope(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: AppTheme.textPrimary,
          ),
        ),
        centerTitle: true,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: _canChangePassword ? _passwordForm() : _googleNotice(),
      ),
    );
  }

  Widget _googleNotice() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.primaryContainer,
            borderRadius: BorderRadius.circular(14),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.info_outline,
                  color: AppTheme.primary, size: 22),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Cuenta vinculada con Google',
                      style: GoogleFonts.manrope(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.primary,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Iniciaste sesión con Google, por lo que no puedes '
                      'cambiar la contraseña desde FallGuard. Tu seguridad '
                      'está gestionada por tu cuenta de Google.',
                      style: GoogleFonts.manrope(
                        fontSize: 13,
                        color: AppTheme.primaryDark,
                        height: 1.4,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        Text(
          'Para cambiar tu contraseña, ve a:',
          style: GoogleFonts.manrope(
            fontSize: 13,
            color: AppTheme.textSecondary,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          'myaccount.google.com → Seguridad → Contraseña',
          style: GoogleFonts.manrope(
            fontSize: 13,
            fontWeight: FontWeight.w700,
            color: AppTheme.textPrimary,
          ),
        ),
      ],
    );
  }

  Widget _passwordForm() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Cambiar contraseña',
          style: GoogleFonts.manrope(
            fontSize: 18,
            fontWeight: FontWeight.w800,
            color: AppTheme.textPrimary,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          'Actualiza tu contraseña periódicamente para mantener tu cuenta segura.',
          style: GoogleFonts.manrope(
            fontSize: 13,
            color: AppTheme.textSecondary,
            height: 1.4,
          ),
        ),
        const SizedBox(height: 24),
        _PasswordField(
          label: 'CONTRASEÑA ACTUAL',
          controller: _currentController,
          obscure: _obscureCurrent,
          onToggle: () => setState(() => _obscureCurrent = !_obscureCurrent),
        ),
        const SizedBox(height: 14),
        _PasswordField(
          label: 'NUEVA CONTRASEÑA',
          controller: _newController,
          obscure: _obscureNew,
          onToggle: () => setState(() => _obscureNew = !_obscureNew),
        ),
        const SizedBox(height: 14),
        _PasswordField(
          label: 'CONFIRMAR NUEVA CONTRASEÑA',
          controller: _confirmController,
          obscure: _obscureConfirm,
          onToggle: () => setState(() => _obscureConfirm = !_obscureConfirm),
        ),
        const SizedBox(height: 24),
        ElevatedButton(
          onPressed: _isLoading ? null : _changePassword,
          child: _isLoading
              ? const SizedBox(
                  height: 20,
                  width: 20,
                  child: CircularProgressIndicator(
                    color: Colors.white,
                    strokeWidth: 2,
                  ),
                )
              : const Text('Cambiar contraseña'),
        ),
        const SizedBox(height: 28),
        const Divider(color: AppTheme.divider),
        const SizedBox(height: 24),
        Text(
          '¿Olvidaste tu contraseña?',
          style: GoogleFonts.manrope(
            fontSize: 15,
            fontWeight: FontWeight.w700,
            color: AppTheme.textPrimary,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          'Te enviaremos un correo con un enlace para restablecerla.',
          style: GoogleFonts.manrope(
            fontSize: 13,
            color: AppTheme.textSecondary,
            height: 1.4,
          ),
        ),
        const SizedBox(height: 14),
        OutlinedButton.icon(
          onPressed: _isLoading ? null : _sendResetEmail,
          icon: const Icon(Icons.mail_outline, size: 18),
          label: const Text('Enviar correo de restablecimiento'),
        ),
      ],
    );
  }
}

class _PasswordField extends StatelessWidget {
  final String label;
  final TextEditingController controller;
  final bool obscure;
  final VoidCallback onToggle;

  const _PasswordField({
    required this.label,
    required this.controller,
    required this.obscure,
    required this.onToggle,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: GoogleFonts.manrope(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: AppTheme.textSecondary,
            letterSpacing: 0.8,
          ),
        ),
        const SizedBox(height: 6),
        Container(
          decoration: BoxDecoration(
            color: AppTheme.surface,
            border: Border.all(color: AppTheme.divider),
            borderRadius: BorderRadius.circular(10),
          ),
          child: TextFormField(
            controller: controller,
            obscureText: obscure,
            style: GoogleFonts.manrope(
              fontSize: 14,
              color: AppTheme.textPrimary,
            ),
            decoration: InputDecoration(
              hintText: '••••••••',
              hintStyle: GoogleFonts.manrope(
                fontSize: 14,
                color: AppTheme.textHint,
              ),
              border: InputBorder.none,
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              suffixIcon: IconButton(
                icon: Icon(
                  obscure
                      ? Icons.visibility_off_outlined
                      : Icons.visibility_outlined,
                  color: AppTheme.iconLight,
                  size: 18,
                ),
                onPressed: onToggle,
              ),
            ),
          ),
        ),
      ],
    );
  }
}
