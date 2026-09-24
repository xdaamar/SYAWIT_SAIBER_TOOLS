import 'package:flutter/material.dart';

import '../services/api.dart';
import '../theme.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  Map<String, dynamic> _settings = {};
  Map<String, dynamic> _paths = {};
  List<dynamic> _wordlists = [];
  final _proxy = TextEditingController();
  final _timeout = TextEditingController();
  final _delay = TextEditingController();
  bool _verifyTls = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final res = await Api.instance.get('/api/settings');
      final wl = await Api.instance.get('/api/settings/wordlists');
      if (!mounted) return;
      setState(() {
        _settings = res['settings'] ?? {};
        _paths = res['paths'] ?? {};
        _wordlists = wl['wordlists'] ?? [];
        _proxy.text = '${_settings['proxy'] ?? ''}';
        _timeout.text = '${_settings['http_timeout'] ?? 10}';
        _delay.text = '${_settings['rate_limit_delay'] ?? 0.2}';
        _verifyTls = _settings['verify_tls'] == true;
      });
    } catch (_) {}
  }

  Future<void> _save() async {
    try {
      await Api.instance.put('/api/settings', {'values': {
        'proxy': _proxy.text.trim(),
        'http_timeout': int.tryParse(_timeout.text) ?? 10,
        'rate_limit_delay': double.tryParse(_delay.text) ?? 0.2,
        'verify_tls': _verifyTls,
      }});
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Settings tersimpan')));
      _load();
    } catch (e) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('gagal: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Settings', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('HTTP', style: TextStyle(fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              TextField(controller: _proxy,
                  decoration: const InputDecoration(
                      labelText: 'Proxy (mis. http://127.0.0.1:8080)', hintText: '-')),
              const SizedBox(height: 10),
              Row(children: [
                SizedBox(width: 160, child: TextField(controller: _timeout,
                    decoration: const InputDecoration(labelText: 'Timeout (detik)'))),
                const SizedBox(width: 10),
                SizedBox(width: 160, child: TextField(controller: _delay,
                    decoration: const InputDecoration(labelText: 'Rate delay (detik)'))),
                const SizedBox(width: 10),
                CheckboxListTile(
                  title: const Text('Verifikasi TLS', style: TextStyle(fontSize: 13)),
                  value: _verifyTls,
                  onChanged: (v) => setState(() => _verifyTls = v ?? false),
                ),
              ]),
              const SizedBox(height: 12),
              FilledButton(onPressed: _save, child: const Text('Simpan')),
            ]),
          ),
        ),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Path data', style: TextStyle(fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              for (final e in _paths.entries)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Text('${e.key}:  ${e.value}',
                      style: const TextStyle(fontSize: 12, color: kMuted)),
                ),
            ]),
          ),
        ),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Wordlists terinstall',
                  style: TextStyle(fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              if (_wordlists.isEmpty)
                const Text('Belum ada — jalankan Setup.',
                    style: TextStyle(color: kMuted, fontSize: 12.5)),
              for (final w in _wordlists)
                ListTile(
                  dense: true,
                  leading: const Icon(Icons.list, size: 16, color: kGreen),
                  title: Text('${w['name']}', style: const TextStyle(fontSize: 13)),
                  subtitle: Text('${w['lines']} baris · ${w['size_kb']} KB',
                      style: const TextStyle(fontSize: 11.5)),
                ),
            ]),
          ),
        ),
      ],
    );
  }
}
