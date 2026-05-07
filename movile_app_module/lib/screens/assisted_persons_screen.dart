import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../theme/app_theme.dart';
import '../services/auth_service.dart';

class AssistedPersonsScreen extends StatefulWidget {
  const AssistedPersonsScreen({super.key});

  @override
  State<AssistedPersonsScreen> createState() =>
      _AssistedPersonsScreenState();
}

class _AssistedPersonsScreenState extends State<AssistedPersonsScreen> {
  final List<_Person> _persons = [];

  @override
  void initState() {
    super.initState();
    final user = AuthService.currentUser;
    _persons.add(_Person(
      name: user?.displayName ?? 'Usuario monitoreado',
      relation: 'Persona principal',
      age: '—',
      notes: 'Monitoreo activo en tiempo real',
    ));
  }

  Future<void> _addPerson() async {
    final nameCtrl = TextEditingController();
    final relCtrl = TextEditingController();
    final ageCtrl = TextEditingController();
    final notesCtrl = TextEditingController();

    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(
          'Agregar persona',
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
                controller: relCtrl,
                decoration: const InputDecoration(labelText: 'Relación'),
              ),
              TextField(
                controller: ageCtrl,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Edad'),
              ),
              TextField(
                controller: notesCtrl,
                decoration: const InputDecoration(labelText: 'Notas'),
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

    if (ok == true && nameCtrl.text.trim().isNotEmpty) {
      setState(() {
        _persons.add(_Person(
          name: nameCtrl.text.trim(),
          relation: relCtrl.text.trim().isEmpty
              ? 'Sin definir'
              : relCtrl.text.trim(),
          age: ageCtrl.text.trim().isEmpty ? '—' : ageCtrl.text.trim(),
          notes: notesCtrl.text.trim(),
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
          'Personas Asistidas',
          style: GoogleFonts.manrope(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: AppTheme.textPrimary,
          ),
        ),
        centerTitle: true,
      ),
      body: ListView.separated(
        padding: const EdgeInsets.all(20),
        itemCount: _persons.length + 1,
        separatorBuilder: (_, __) => const SizedBox(height: 12),
        itemBuilder: (_, i) {
          if (i == _persons.length) {
            return OutlinedButton.icon(
              onPressed: _addPerson,
              icon: const Icon(Icons.person_add_alt_1_outlined, size: 20),
              label: const Text('Agregar persona'),
            );
          }
          return _personCard(_persons[i], i);
        },
      ),
    );
  }

  Widget _personCard(_Person p, int index) {
    return Container(
      padding: const EdgeInsets.all(16),
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
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              color: AppTheme.primaryContainer,
              shape: BoxShape.circle,
              border: Border.all(
                color: AppTheme.primary.withValues(alpha: 0.2),
                width: 2,
              ),
            ),
            child: const Icon(
              Icons.elderly,
              color: AppTheme.primary,
              size: 28,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  p.name,
                  style: GoogleFonts.manrope(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${p.relation} · ${p.age} años',
                  style: GoogleFonts.manrope(
                    fontSize: 12,
                    color: AppTheme.textSecondary,
                  ),
                ),
                if (p.notes.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(
                    p.notes,
                    style: GoogleFonts.manrope(
                      fontSize: 12,
                      color: AppTheme.textSecondary,
                      height: 1.4,
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (index > 0)
            IconButton(
              icon: const Icon(Icons.delete_outline,
                  color: AppTheme.iconLight, size: 20),
              onPressed: () => setState(() => _persons.removeAt(index)),
            ),
        ],
      ),
    );
  }
}

class _Person {
  final String name;
  final String relation;
  final String age;
  final String notes;
  const _Person({
    required this.name,
    required this.relation,
    required this.age,
    required this.notes,
  });
}
