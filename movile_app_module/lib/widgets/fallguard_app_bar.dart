import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../theme/app_theme.dart';

class FallGuardAppBar extends StatelessWidget implements PreferredSizeWidget {
  final bool showAvatar;
  final bool showBell;
  final VoidCallback? onBellTap;
  final VoidCallback? onAvatarTap;

  const FallGuardAppBar({
    super.key,
    this.showAvatar = true,
    this.showBell = true,
    this.onBellTap,
    this.onAvatarTap,
  });

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);

  @override
  Widget build(BuildContext context) {
    return AppBar(
      backgroundColor: AppTheme.background,
      elevation: 0,
      scrolledUnderElevation: 0,
      titleSpacing: 20,
      title: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.shield, color: AppTheme.primary, size: 20),
          const SizedBox(width: 6),
          Text(
            'FallGuard',
            style: GoogleFonts.manrope(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: AppTheme.primary,
            ),
          ),
        ],
      ),
      actions: [
        if (showBell)
          IconButton(
            icon: const Icon(
              Icons.notifications_outlined,
              color: AppTheme.textPrimary,
              size: 24,
            ),
            onPressed: onBellTap,
          ),
        if (showAvatar)
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: GestureDetector(
              onTap: onAvatarTap,
              child: const CircleAvatar(
                radius: 18,
                backgroundColor: AppTheme.primaryContainer,
                child: Icon(
                  Icons.person,
                  color: AppTheme.primary,
                  size: 20,
                ),
              ),
            ),
          ),
      ],
    );
  }
}
