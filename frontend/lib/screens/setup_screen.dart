import 'dart:async';

import 'package:flutter/material.dart';

import '../services/api.dart';
import '../theme.dart';
import '../widgets/command_preview.dart';

class SetupScreen extends StatefulWidget {
  const SetupScreen({super.key});

  @override
  State<SetupScreen> createState() => _SetupScreenState();
}

class _SetupScreenState extends State<SetupScreen> {
  List<dynamic> _components = [];
  bool _running = false;
  bool? _ready;
  final List<String> _log = [];
  StreamSubscription<Map<String, dynamic>>? _sub;
  final ScrollController _logScroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _refresh();
    _listen();
  }

  Future<void> _refresh() async {
    try {
      final status = await Api.instance.get('/api/setup/status');
      if (!mounted) return;
      setState(() {
        _components = status['components'] ?? [];
        _running = status['running'] == true;
        _ready = status['ready'] == true;
      });
    } catch (e) {
      _log.add('[!] gagal memuat status: $e');
    }
  }

  void _listen() {
    _sub = Api.instance.setupEvents().listen((msg) {
      if (!mounted) return;
      final ev = msg['event'];
      if (ev == 'log') {
        setState(() {
          _log.add('${msg['line']}');
        });
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (_logScroll.hasClients) {
            _logScroll.jumpTo(_logScroll.position.maxScrollExtent);
          }
        });
      } else if (ev == 'step') {
        setState(() {
          _log.add('[step] ${msg['component']} -> ${msg['status']}');
        });
      } else if (ev == 'start') {
        setState(() {
          _running = true;
          _log.clear();
          _log.add('=== setup dimulai ===');
        });
      } else if (ev == 'done') {
        setState(() {
          _running = false;
          _log.add('=== selesai. ready=${msg['ready']} ===');
        });
        _refresh();
      } else if (ev == 'cancelled') {
        setState(() => _running = false);
        _refresh();
      }
    });
  }

  Future<void> _runSetup() async {
    final ok = await CommandPreviewDialog.confirm(
      context,
      title: 'Smart Setup — install/sinkron komponen yang kurang',
      command: 'backend: setup.run()  (komponen OK di-skip, tidak diinstall ulang)',
      warning: 'Beberapa komponen (nmap) bisa meminta izin UAC Windows.',
    );
    if (!ok) return;
    try {
      await Api.instance.post('/api/setup/run', {'only': null});
      setState(() {
        _running = true;
        _log.clear();
      });
    } on ApiException catch (e) {
      _log.add('[!] ${e.message}');
    }
  }

  Future<void> _cancel() async {
    await Api.instance.post('/api/setup/cancel');
  }

  Future<void> _doctor(String? component) async {
    try {
      final q = component == null ? '' : '?component=$component';
      final report = await Api.instance.get('/api/setup/doctor$q');
      if (!mounted) return;
      showDialog(
        context: context,
        builder: (_) => AlertDialog(
          backgroundColor: kSurface,
          title: Text('Doctor${component != null ? ' — $component' : ''}'),
          content: SizedBox(
            width: 520,
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('${report['summary']}',
                      style: const TextStyle(color: kMuted)),
                  const Divider(),
                  for (final f in (report['findings'] as List? ?? []))
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 3),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(
                            f['level'] == 'error'
                                ? Icons.error
                                : f['level'] == 'warn'
                                    ? Icons.warning_amber
                                    : Icons.check_circle,
                            size: 16,
                            color: f['level'] == 'error'
                                ? kRed
                                : f['level'] == 'warn'
                                    ? kYellow
                                    : kGreen,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                              child: Text('${f['message']}',
                                  style: const TextStyle(fontSize: 12.5))),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Tutup')),
          ],
        ),
      );
    } catch (e) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('doctor gagal: $e')));
    }
  }

  Future<void> _retry(String name) async {
    try {
      await Api.instance.post('/api/setup/retry/$name');
      setState(() => _running = true);
    } catch (e) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('retry gagal: $e')));
    }
  }

  @override
  void dispose() {
    _sub?.cancel();
    _logScroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Text('Smart Setup', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(width: 12),
            if (_ready != null)
              Chip(
                backgroundColor:
                    (_ready! ? kGreen : kYellow).withOpacity(.15),
                label: Text(_ready! ? 'READY' : 'BELUM SIAP',
                    style: TextStyle(
                        color: _ready! ? kGreen : kYellow,
                        fontWeight: FontWeight.bold)),
              ),
            const Spacer(),
            OutlinedButton.icon(
              onPressed: () => _doctor(null),
              icon: const Icon(Icons.medical_information_outlined, size: 18),
              label: const Text('Doctor'),
            ),
            const SizedBox(width: 8),
            _running
                ? FilledButton.icon(
                    style: FilledButton.styleFrom(
                        backgroundColor: kRed, foregroundColor: Colors.white),
                    onPressed: _cancel,
                    icon: const Icon(Icons.stop, size: 18),
                    label: const Text('Stop'))
                : FilledButton.icon(
                    onPressed: _runSetup,
                    icon: const Icon(Icons.rocket_launch_outlined, size: 18),
                    label: const Text('Jalankan Setup')),
          ]),
          const SizedBox(height: 8),
          Text(
            'Komponen yang sudah OK tidak akan diinstall ulang. Error diklasifikasi '
            'otomatis dengan saran perbaikan; log lengkap tersimpan di folder logs.',
            style: const TextStyle(color: kMuted, fontSize: 12.5),
          ),
          const SizedBox(height: 12),
          Expanded(
            flex: 3,
            child: Card(
              child: ListView.separated(
                itemCount: _components.length,
                separatorBuilder: (_, __) => const Divider(height: 1),
                itemBuilder: (_, i) {
                  final c = _components[i] as Map<String, dynamic>;
                  final st = '${c['status']}';
                  return ListTile(
                    dense: true,
                    leading: Icon(_iconFor(st), color: statusColor(st), size: 20),
                    title: Text('${c['title']}',
                        style: const TextStyle(fontSize: 14)),
                    subtitle: Text(
                        'status: $st  ·  versi: ${c['version'] ?? '-'}'
                        '${c['required'] != null ? '  ·  min: ${c['required']}' : ''}',
                        style: const TextStyle(fontSize: 12)),
                    trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                      if (c['optional'] == true)
                        const Padding(
                          padding: EdgeInsets.only(right: 8),
                          child: Text('opsional',
                              style: TextStyle(fontSize: 11, color: kMuted)),
                        ),
                      if (st == 'error')
                        TextButton(
                            onPressed: () => _retry('${c['component']}'),
                            child: const Text('Retry')),
                      TextButton(
                          onPressed: () => _doctor('${c['component']}'),
                          child: const Text('Diagnose')),
                    ]),
                  );
                },
              ),
            ),
          ),
          const SizedBox(height: 12),
          Expanded(
            flex: 2,
            child: Container(
              width: double.infinity,
              decoration: BoxDecoration(
                color: const Color(0xFF0A0C10),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: const Color(0xFF30363D)),
              ),
              padding: const EdgeInsets.all(10),
              child: _log.isEmpty
                  ? const Center(
                      child: Text('Log setup akan muncul di sini.',
                          style: TextStyle(color: kMuted)))
                  : ListView.builder(
                      controller: _logScroll,
                      itemCount: _log.length,
                      itemBuilder: (_, i) => Text(_log[i],
                          style: const TextStyle(
                              fontFamily: 'Consolas, Courier New, monospace',
                              fontSize: 12.5,
                              color: Colors.white70)),
                    ),
            ),
          ),
        ],
      ),
    );
  }

  IconData _iconFor(String st) {
    switch (st) {
      case 'ok':
        return Icons.check_circle;
      case 'missing':
        return Icons.cancel;
      case 'outdated':
        return Icons.update;
      case 'broken':
        return Icons.build;
      case 'partial':
        return Icons.remove_circle_outline;
      default:
        return Icons.help_outline;
    }
  }
}
