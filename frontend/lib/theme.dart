import 'package:flutter/material.dart';

const kBg = Color(0xFF0F1115);
const kSurface = Color(0xFF171A21);
const kCard = Color(0xFF1C2029);
const kGreen = Color(0xFF7EE787);
const kAccent = Color(0xFF58A6FF);
const kOrange = Color(0xFFFFA657);
const kRed = Color(0xFFFF7B72);
const kYellow = Color(0xFFE3B341);
const kMuted = Color(0xFF8B949E);

ThemeData buildTheme() {
  final scheme = ColorScheme.dark(
    surface: kSurface,
    primary: kGreen,
    secondary: kAccent,
    error: kRed,
  );
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: kBg,
    appBarTheme: const AppBarTheme(
      backgroundColor: kSurface,
      foregroundColor: Colors.white,
      elevation: 0,
    ),
    cardTheme: const CardThemeData(color: kCard, elevation: 0),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: kSurface,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: Color(0xFF30363D)),
      ),
      labelStyle: const TextStyle(color: kMuted),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(backgroundColor: kGreen, foregroundColor: Colors.black),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(foregroundColor: kAccent),
    ),
    textTheme: const TextTheme(
      bodyMedium: TextStyle(color: Colors.white70),
      titleMedium: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
    ),
    chipTheme: const ChipThemeData(backgroundColor: kCard, labelStyle: TextStyle(color: Colors.white70)),
    dividerColor: const Color(0xFF30363D),
  );
}

Color sevColor(String severity) {
  switch (severity.toLowerCase()) {
    case 'critical':
      return kRed;
    case 'high':
      return kOrange;
    case 'medium':
      return kYellow;
    case 'low':
      return kAccent;
    default:
      return kMuted;
  }
}

Color statusColor(String status) {
  switch (status) {
    case 'ok':
    case 'done':
    case 'installed':
      return kGreen;
    case 'missing':
    case 'failed':
      return kRed;
    case 'outdated':
    case 'partial':
      return kYellow;
    case 'broken':
      return kOrange;
    default:
      return kMuted;
  }
}
