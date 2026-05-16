import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../theme/app_theme.dart';
import '../services/auth_service.dart';

class EditProfileScreen extends StatefulWidget {
  const EditProfileScreen({super.key});

  @override
  State<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends State<EditProfileScreen> {
  late final TextEditingController _nameController;
  late final String _email;
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    final user = AuthService.currentUser;
    _nameController = TextEditingController(text: user?.displayName ?? '');
    _email = user?.email ?? '';
  }

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final name = _nameController.text.trim();
    if (name.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('El nombre no puede estar vacío')),
      );
      return;
    }
    setState(() => _isLoading = true);
    final error = await AuthService.updateDisplayName(name);
    if (!mounted) return;
    setState(() => _isLoading = false);

    if (error != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error), backgroundColor: AppTheme.alertRed),
      );
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Perfil actualizado correctamente')),
    );
    Navigator.pop(context);
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
          'Editar Perfil',
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
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            const SizedBox(height: 8),
            Container(
              width: 96,
              height: 96,
              decoration: BoxDecoration(
                color: AppTheme.primaryContainer,
                shape: BoxShape.circle,
                border: Border.all(
                  color: AppTheme.primary.withValues(alpha: 0.2),
                  width: 3,
                ),
              ),
              child: const Icon(
                Icons.person,
                size: 50,
                color: AppTheme.primary,
              ),
            ),
            const SizedBox(height: 28),
            _LabeledField(
              label: 'NOMBRE COMPLETO',
              controller: _nameController,
              hint: 'Tu nombre',
            ),
            const SizedBox(height: 16),
            _LabeledField(
              label: 'CORREO ELECTRÓNICO',
              controller: TextEditingController(text: _email),
              hint: '',
              enabled: false,
            ),
            const SizedBox(height: 32),
            ElevatedButton(
              onPressed: _isLoading ? null : _save,
              child: _isLoading
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(
                        color: Colors.white,
                        strokeWidth: 2,
                      ),
                    )
                  : const Text('Guardar cambios'),
            ),
          ],
        ),
      ),
    );
  }
}

class _LabeledField extends StatelessWidget {
  final String label;
  final TextEditingController controller;
  final String hint;
  final bool enabled;

  const _LabeledField({
    required this.label,
    required this.controller,
    required this.hint,
    this.enabled = true,
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
            color: enabled ? AppTheme.surface : const Color(0xFFF3F3F3),
            border: Border.all(color: AppTheme.divider),
            borderRadius: BorderRadius.circular(10),
          ),
          child: TextFormField(
            controller: controller,
            enabled: enabled,
            style: GoogleFonts.manrope(
              fontSize: 14,
              color: enabled ? AppTheme.textPrimary : AppTheme.textSecondary,
            ),
            decoration: InputDecoration(
              hintText: hint,
              hintStyle: GoogleFonts.manrope(
                fontSize: 14,
                color: AppTheme.textHint,
              ),
              border: InputBorder.none,
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            ),
          ),
        ),
      ],
    );
  }
}
