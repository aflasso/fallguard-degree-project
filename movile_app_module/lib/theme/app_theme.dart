import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  AppTheme._();

  // Brand colors
  static const Color primary = Color(0xFF005E53);
  static const Color primaryDark = Color(0xFF004A41);
  static const Color primaryContainer = Color(0xFFDFF0EE);
  static const Color background = Color(0xFFF6FAFA);
  static const Color surface = Color(0xFFFFFFFF);

  // Alert colors
  static const Color alertRed = Color(0xFFD32F2F);
  static const Color alertRedLight = Color(0xFFFFF0F0);

  // Warning colors (módulo desconectado, avisos no críticos)
  static const Color warning = Color(0xFFE8A317);
  static const Color warningLight = Color(0xFFFFF6E5);

  // Text colors
  static const Color textPrimary = Color(0xFF111827);
  static const Color textSecondary = Color(0xFF6B7280);
  static const Color textHint = Color(0xFFD1D5DB);
  static const Color iconLight = Color(0xFF9CA3AF);
  static const Color divider = Color(0xFFE5E7EB);

  static TextStyle manrope({
    double fontSize = 14,
    FontWeight fontWeight = FontWeight.w400,
    Color color = textPrimary,
    double? letterSpacing,
    double? height,
  }) =>
      GoogleFonts.manrope(
        fontSize: fontSize,
        fontWeight: fontWeight,
        color: color,
        letterSpacing: letterSpacing,
        height: height,
      );

  static ThemeData get theme {
    final base = ThemeData(useMaterial3: true);
    return base.copyWith(
      colorScheme: ColorScheme.fromSeed(
        seedColor: primary,
        primary: primary,
        secondary: primary,
        surface: surface,
        brightness: Brightness.light,
      ),
      scaffoldBackgroundColor: background,
      textTheme: GoogleFonts.manropeTextTheme(base.textTheme),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: Colors.white,
          minimumSize: const Size(double.infinity, 54),
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(30),
          ),
          textStyle: GoogleFonts.manrope(
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: primary,
          minimumSize: const Size(double.infinity, 54),
          elevation: 0,
          side: const BorderSide(color: Color(0xFFD1D5DB), width: 1.5),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(30),
          ),
          textStyle: GoogleFonts.manrope(
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: false,
        contentPadding: const EdgeInsets.only(top: 8, bottom: 8),
        border: const UnderlineInputBorder(
          borderSide: BorderSide(color: divider),
        ),
        enabledBorder: const UnderlineInputBorder(
          borderSide: BorderSide(color: divider),
        ),
        focusedBorder: const UnderlineInputBorder(
          borderSide: BorderSide(color: primary, width: 2),
        ),
        labelStyle: GoogleFonts.manrope(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: textSecondary,
          letterSpacing: 0.8,
        ),
        hintStyle: GoogleFonts.manrope(
          fontSize: 14,
          color: textHint,
        ),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: background,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleSpacing: 0,
      ),
      cardTheme: CardThemeData(
        color: surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
        margin: EdgeInsets.zero,
      ),
      bottomNavigationBarTheme: BottomNavigationBarThemeData(
        backgroundColor: surface,
        selectedItemColor: primary,
        unselectedItemColor: iconLight,
        type: BottomNavigationBarType.fixed,
        elevation: 0,
        selectedLabelStyle: GoogleFonts.manrope(
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
        unselectedLabelStyle: GoogleFonts.manrope(
          fontSize: 11,
          fontWeight: FontWeight.w400,
        ),
      ),
      dividerTheme: const DividerThemeData(
        color: divider,
        thickness: 1,
        space: 1,
      ),
    );
  }
}
