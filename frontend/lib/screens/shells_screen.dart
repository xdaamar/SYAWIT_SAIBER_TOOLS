import 'package:flutter/material.dart';

import '../services/api.dart';
import '../theme.dart';
import '../widgets/terminal_box.dart';

class ShellsScreen extends StatefulWidget {
  const ShellsScreen({super.key});

  @override
  State<ShellsScreen> createState() => _ShellsScreenState();
}

class _ShellsScreenState extends State<ShellsScreen> {
  final _lhost = TextEditingController(text: '127.0.0.1');
  final _lport = TextEditingController(text: '4444');
  List<dynamic> _reverse = [];
  List<dynamic> _bind = [];
  List<dynamic> _listeners = [];
  int _listenerPort = 4444;
  String? _jobId;
  final _sendCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _genPayloads();
    _refreshListeners();
  }

  Future<void> _genPayloads() async {
    try {
      final res = await Api.instance.post('/api/shells/payloads', {
        'lhost': _lhost.text.trim(), 'lport': int.tryParse(_lport.text) ?? 4444,
      });
      if (!mounted) return;
      setState(() {
        _reverse = res['reverse'] ?? [];
        _bind = res['bind'] ?? [];
      });
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _refreshListeners() async {
    try {
      final res = await Api.instance.get('/api/shells/listener');
      if (!mounted) return;
      setState(() => _listeners = res['listeners'] ?? []);
    } catch (_) {}
  }

  Future<void> _startListener() async {
    try {
      _listenerPort = int.tryParse(_lport.text) ?? 4444;
      await Api.instance.post('/api/shells/listener/start',
          {'port': _listenerPort, 'host': '0.0.0.0'});
      _snack('listener aktif di port $_listenerPort');
      _refreshListeners();
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _sendCmd(String cmd) async {
    try {
      await Api.instance.post('/api/shells/$_listenerPort/send',
          {'command': cmd});
      _snack('terkirim: $cmd');
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _stopListener() async {
    try {
      await Api.instance.post('/api/shells/$_listenerPort/stop');
      _snack('listener di-stop');
      _refreshListeners();
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _genWebshell() async {
    final secret = await _ask('Secret param (kosongkan = tanpa secret)');
    if (secret == null) return;
    try {
      final res = await Api.instance.post('/api/shells/webshell',
          {'kind': 'php', 'secret': secret});
      if (!mounted) return;
      _showText('PHP webshell (HANYA untuk lab milikmu)', res['code']);
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<String?> _ask(String label) async {
    final ctrl = TextEditingController();
    final res = await showDialog<String>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: kSurface,
        title: Text(label),
        content: TextField(controller: ctrl),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Batal')),
          FilledButton(onPressed: () => Navigator.pop(context, ctrl.text.trim()),
              child: const Text('OK')),
        ],
      ),
    );
    return res;
  }

  void _showText(String title, String text) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: kSurface,
        title: Text(title),
        content: Container(
          constraints: const BoxConstraints(maxWidth: 640, maxHeight: 420),
          decoration: BoxDecoration(
            color: const Color(0xFF0A0C10),
            borderRadius: BorderRadius.circular(8),
          ),
          padding: const EdgeInsets.all(10),
          child: SingleChildScrollView(
              child: SelectableText(text,
                  style: const TextStyle(
                      fontFamily: 'Consolas, Courier New, monospace',
                      fontSize: 12, color: kGreen))),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context),
              child: const Text('Tutup')),
        ],
      ),
    );
  }

  void _snack(String msg) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Shells',
              style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 12),
          Row(children: [
            SizedBox(width: 220, child: TextField(controller: _lhost,
                decoration: const InputDecoration(labelText: 'LHOST'))),
            const SizedBox(width: 8),
            SizedBox(width: 120, child: TextField(controller: _lport,
                decoration: const InputDecoration(labelText: 'LPORT'))),
            const SizedBox(width: 8),
            FilledButton(onPressed: _genPayloads,
                child: const Text('Generate payload')),
            const SizedBox(width: 8),
            OutlinedButton(onPressed: _genWebshell,
                child: const Text('Webshell PHP')),
            const SizedBox(width: 8),
            OutlinedButton(onPressed: _startListener,
                child: const Text('Start listener')),
            const SizedBox(width: 8),
            OutlinedButton(onPressed: _stopListener,
                child: const Text('Stop listener')),
          ]),
          const SizedBox(height: 12),
          Expanded(
            flex: 4,
            child: Card(
              child: ListView(
                padding: const EdgeInsets.all(8),
                children: [
                  const Padding(
                    padding: EdgeInsets.all(8),
                    child: Text('Reverse shells (klik untuk copy)',
                        style: TextStyle(fontWeight: FontWeight.bold)),
                  ),
                  for (final p in _reverse)
                    ListTile(
                      dense: true,
                      leading: Icon(
                        '${p['os']}' == 'windows'
                            ? Icons.desktop_windows
                            : Icons.terminal,
                        size: 18, color: kAccent),
                      title: Text('${p['name']}',
                          style: const TextStyle(fontSize: 13)),
                      subtitle: SelectableText('${p['payload']}',
                          maxLines: 1,
                          style: const TextStyle(
                              fontFamily: 'Consolas, Courier New, monospace',
                              fontSize: 11.5, color: Colors.white60)),
                      trailing: const Icon(Icons.copy, size: 14, color: kMuted),
                      onTap: () => _snack('payload tersalin'),
                    ),
                  const Divider(),
                  for (final p in _bind)
                    ListTile(
                      dense: true,
                      leading: const Icon(Icons.dns, size: 18, color: kAccent),
                      title: Text('${p['name']} (bind)',
                          style: const TextStyle(fontSize: 13)),
                      subtitle: SelectableText('${p['payload']}',
                          maxLines: 1,
                          style: const TextStyle(
                              fontFamily: 'Consolas, Courier New, monospace',
                              fontSize: 11.5, color: Colors.white60)),
                    ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 10),
          Expanded(
            flex: 2,
            child: Column(children: [
              Row(children: [
                Text('Listener $_listenerPort',
                    style: const TextStyle(fontWeight: FontWeight.bold)),
                const Spacer(),
                for (final l in _listeners)
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: Chip(
                        visualDensity: VisualDensity.compact,
                        label: Text('port ${l['port']} — '
                            '${(l['connections'] as List?)?.length ?? 0} koneksi')),
                  ),
                const SizedBox(width: 8),
                SizedBox(
                  width: 260,
                  child: TextField(
                    controller: _sendCtrl,
                    decoration: const InputDecoration(
                        labelText: 'Kirim command ke shell', isDense: true),
                    onSubmitted: (v) {
                      if (v.trim().isNotEmpty) {
                        _sendCmd(v.trim());
                        _sendCtrl.clear();
                      }
                    },
                  ),
                ),
              ]),
              Expanded(child: TerminalBox(jobId: _jobId)),
            ]),
          ),
        ],
      ),
    );
  }
}
