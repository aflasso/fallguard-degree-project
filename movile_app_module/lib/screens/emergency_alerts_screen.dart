import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../theme/app_theme.dart';

class EmergencyAlertsScreen extends StatefulWidget {
  const EmergencyAlertsScreen({super.key});

  @override
  State<EmergencyAlertsScreen> createState() =>
      _EmergencyAlertsScreenState();
}

class _EmergencyAlertsScreenState extends State<EmergencyAlertsScreen> {
  bool _sirenEnabled = true;
  bool _smsEnabled = true;
  bool _autoCallEnabled = false;
  double _sirenVolume = 0.8;

  final List<_Contact> _contacts = [
    const _Contact('María Pérez', '+57 311 234 5678', 'Hija'),
    const _Contact('Carlos Pérez', '+57 314 555 9876', 'Hijo'),
  ];

  Future<void> _addContact() async {
    final nameCtrl = TextEditingController();
    final phoneCtrl = TextEditingController();
    final relCtrl = TextEditingController();

    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(
          'Agregar contacto',
          style: GoogleFonts.manrope(fontWeight: FontWeight.w700),
        ),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: nameCtrl,
                decoration: const InputDecoration(labelText: 'Nombre'),
              ),
              TextField(
                controller: phoneCtrl,
                keyboardType: TextInputType.phone,
                decoration: const InputDecoration(labelText: 'Teléfono'),
              ),
              TextField(
                controller: relCtrl,
                decoration: const InputDecoration(labelText: 'Relación'),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancelar'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Agregar'),
          ),
        ],
      ),
    );

    if (result == true && nameCtrl.text.trim().isNotEmpty) {
      setState(() {
        _contacts.add(_Contact(
          nameCtrl.text.trim(),
          phoneCtrl.text.trim(),
          relCtrl.text.trim(),
        ));
      });
    }
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
          'Alertas de Emergencia',
          style: GoogleFonts.manrope(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: AppTheme.textPrimary,
          ),
        ),
        centerTitle: true,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle('NOTIFICACIONES'),
            _card(Column(
              children: [
                _switchTile(
                  icon: Icons.volume_up_outlined,
                  title: 'Sirena al detectar caída',
                  subtitle: 'Reproduce un sonido de alerta',
                  value: _sirenEnabled,
                  onChanged: (v) => setState(() => _sirenEnabled = v),
                ),
                const Divider(height: 1, color: AppTheme.divider),
                _switchTile(
                  icon: Icons.sms_outlined,
                  title: 'Notificación SMS',
                  subtitle: 'Envía SMS a contactos de emergencia',
                  value: _smsEnabled,
                  onChanged: (v) => setState(() => _smsEnabled = v),
                ),
                const Divider(height: 1, color: AppTheme.divider),
                _switchTile(
                  icon: Icons.call_outlined,
                  title: 'Llamada automática',
                  subtitle: 'Llama al primer contacto de la lista',
                  value: _autoCallEnabled,
                  onChanged: (v) => setState(() => _autoCallEnabled = v),
                ),
              ],
            )),
            const SizedBox(height: 20),
            _sectionTitle('VOLUMEN DE SIRENA'),
            _card(Padding(
              padding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Row(
                children: [
                  const Icon(Icons.volume_down,
                      color: AppTheme.iconLight, size: 20),
                  Expanded(
                    child: Slider(
                      value: _sirenVolume,
                      onChanged: _sirenEnabled
                          ? (v) => setState(() => _sirenVolume = v)
                          : null,
                      activeColor: AppTheme.primary,
                    ),
                  ),
                  const Icon(Icons.volume_up,
                      color: AppTheme.iconLight, size: 20),
                ],
              ),
            )),
            const SizedBox(height: 20),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                _sectionTitle('CONTACTOS DE EMERGENCIA'),
                TextButton.icon(
                  onPressed: _addContact,
                  icon: const Icon(Icons.add, size: 18),
                  label: Text(
                    'Agregar',
                    style: GoogleFonts.manrope(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.primary,
                    ),
                  ),
                ),
              ],
            ),
            _card(Column(
              children: _contacts
                  .asMap()
                  .entries
                  .expand((e) => [
                        _contactTile(e.value, e.key),
                        if (e.key != _contacts.length - 1)
                          const Divider(
                              height: 1, color: AppTheme.divider),
                      ])
                  .toList(),
            )),
            const SizedBox(height: 28),
          ],
        ),
      ),
    );
  }

  Widget _sectionTitle(String text) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 8),
      child: Text(
        text,
        style: GoogleFonts.manrope(
          fontSize: 11,
          fontWeight: FontWeight.w700,
          color: AppTheme.textSecondary,
          letterSpacing: 0.8,
        ),
      ),
    );
  }

  Widget _card(Widget child) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(14),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 10,
          ),
        ],
      ),
      child: child,
    );
  }

  Widget _switchTile({
    required IconData icon,
    required String title,
    required String subtitle,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: AppTheme.background,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: AppTheme.textSecondary, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: GoogleFonts.manrope(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                  ),
                ),
                Text(
                  subtitle,
                  style: GoogleFonts.manrope(
                    fontSize: 12,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
            thumbColor: WidgetStateProperty.resolveWith(
              (states) => states.contains(WidgetState.selected)
                  ? AppTheme.primary
                  : null,
            ),
          ),
        ],
      ),
    );
  }

  Widget _contactTile(_Contact contact, int index) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          CircleAvatar(
            radius: 20,
            backgroundColor: AppTheme.primaryContainer,
            child: Text(
              contact.name.isNotEmpty ? contact.name[0].toUpperCase() : '?',
              style: GoogleFonts.manrope(
                fontWeight: FontWeight.w700,
                color: AppTheme.primary,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  contact.name,
                  style: GoogleFonts.manrope(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  ),
                ),
                Text(
                  '${contact.phone} · ${contact.relation}',
                  style: GoogleFonts.manrope(
                    fontSize: 12,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.delete_outline,
                color: AppTheme.iconLight, size: 20),
            onPressed: () => setState(() => _contacts.removeAt(index)),
          ),
        ],
      ),
    );
  }
}

class _Contact {
  final String name;
  final String phone;
  final String relation;
  const _Contact(this.name, this.phone, this.relation);
}
