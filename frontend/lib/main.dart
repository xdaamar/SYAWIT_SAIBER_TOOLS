import 'package:flutter/material.dart';

import 'screens/crypto_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/jobs_screen.dart';
import 'screens/pwn_screen.dart';
import 'screens/recon_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/setup_screen.dart';
import 'screens/shells_screen.dart';
import 'screens/web_screen.dart';
import 'services/api.dart';
import 'services/backend.dart';
import 'theme.dart';

void main() {
  runApp(const CtfSuiteApp());
}

class CtfSuiteApp extends StatelessWidget {
  const CtfSuiteApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CTFSuite',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(),
      home: const BootGate(),
      routes: {
        '/recon': (_) => const ReconScreen(),
        '/web': (_) => const WebScreen(),
        '/crypto': (_) => const CryptoScreen(),
        '/pwn': (_) => const PwnScreen(),
        '/shells': (_) => const ShellsScreen(),
        '/jobs': (_) => const JobsScreen(),
        '/settings': (_) => const SettingsScreen(),
        '/setup': (_) => const SetupScreen(),
      },
    );
  }
}

/// Waits for backend readiness, then enforces the first-run disclaimer.
class BootGate extends StatefulWidget {
  const BootGate({super.key});

  @override
  State<BootGate> createState() => _BootGateState();
}

class _BootGateState extends State<BootGate> {
  bool? _ready; // null = loading
  String? _error;

  @override
  void initState() {
    super.initState();
    _boot();
  }

  Future<void> _boot() async {
    setState(() {
      _ready = null;
      _error = null;
    });
    await BackendService.instance.start();
    if (!mounted) return;
    if (!BackendService.instance.ready) {
      setState(() {
        _ready = false;
        _error = BackendService.instance.lastError;
      });
      return;
    }
    // disclaimer check
    try {
      final settings = await Api.instance.get('/api/settings');
      final accepted = settings['disclaimer_accepted'] == true;
      if (!mounted) return;
      if (!accepted) {
        _showDisclaimer();
      }
      setState(() => _ready = true);
    } catch (e) {
      setState(() {
        _ready = false;
        _error = '$e';
      });
    }
  }

  Future<void> _showDisclaimer() async {
    final accepted = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        backgroundColor: kSurface,
        title: Row(children: const [
          Icon(Icons.warning_amber_rounded, color: kYellow),
          SizedBox(width: 8),
          Text('Disclaimer'),
        ]),
        content: const SingleChildScrollView(
          child: Text(
            'CTFSuite adalah alat keamanan untuk CTF dan pengujian penetrasi '
            'pada sistem yang ANDA MILIKI atau punya IZIN EKSPLISIT untuk diuji.\n\n'
            'Menjalankan tools ini terhadap sistem tanpa izin adalah ILEGAL. '
            'Kamu bertanggung jawab penuh atas penggunaan tools ini.\n\n'
            'Setiap aksi eksekusi akan selalu menampilkan preview perintah '
            'sebelum dijalankan.',
            style: TextStyle(fontSize: 13.5, height: 1.5),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keluar'),
          ),
          FilledButton(
            onPressed: () async {
              try {
                await Api.instance.post('/api/settings/accept-disclaimer');
              } catch (_) {}
              if (context.mounted) Navigator.pop(context, true);
            },
            child: const Text('Saya mengerti & setuju'),
          ),
        ],
      ),
    );
    if (accepted != true && mounted) {
      // exit app if refused
      await Future.delayed(const Duration(milliseconds: 100));
      // ignore: use_build_context_synchronously
      Navigator.of(context).popUntil((_) => false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_ready == null) {
      return const Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('Memulai backend CTFSuite...'),
            ],
          ),
        ),
      );
    }
    if (_ready == false) {
      return Scaffold(
        body: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Backend gagal start',
                        style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 12),
                    SelectableText(_error ?? 'tidak diketahui'),
                    const SizedBox(height: 16),
                    FilledButton(onPressed: _boot, child: const Text('Coba lagi')),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
    }
    return const HomeShell();
  }
}

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  static const _destinations = [
    (Icons.dashboard_outlined, 'Dashboard'),
    (Icons.build_circle_outlined, 'Setup'),
    (Icons.radar, 'Recon'),
    (Icons.language, 'Web'),
    (Icons.enhanced_encryption_outlined, 'Crypto'),
    (Icons.memory_outlined, 'Pwn'),
    (Icons.terminal, 'Shells'),
    (Icons.list_alt, 'Jobs'),
    (Icons.settings_outlined, 'Settings'),
  ];

  static const _screens = [
    DashboardScreen(),
    SetupScreen(),
    ReconScreen(),
    WebScreen(),
    CryptoScreen(),
    PwnScreen(),
    ShellsScreen(),
    JobsScreen(),
    SettingsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          NavigationRail(
            backgroundColor: kSurface,
            selectedIndex: _index,
            onDestinationSelected: (i) => setState(() => _index = i),
            labelType: NavigationRailLabelType.all,
            leading: const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Column(children: [
                Icon(Icons.security, color: kGreen, size: 28),
                SizedBox(height: 4),
                Text('CTFSuite',
                    style: TextStyle(fontSize: 11, color: kMuted)),
              ]),
            ),
            destinations: [
              for (final d in _destinations)
                NavigationRailDestination(
                  icon: Icon(d.$1, size: 20),
                  label: Text(d.$2, style: const TextStyle(fontSize: 11)),
                ),
            ],
          ),
          const VerticalDivider(width: 1),
          Expanded(child: _screens[_index]),
        ],
      ),
    );
  }
}
