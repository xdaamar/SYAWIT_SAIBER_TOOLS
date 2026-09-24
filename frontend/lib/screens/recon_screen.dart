import 'package:flutter/material.dart';

import '../services/api.dart';
import '../theme.dart';
import '../widgets/command_preview.dart';
import '../widgets/terminal_box.dart';

class ReconScreen extends StatefulWidget {
  const ReconScreen({super.key});

  @override
  State<ReconScreen> createState() => _ReconScreenState();
}

class _ReconScreenState extends State<ReconScreen> {
  final _target = TextEditingController();
  final _extra = TextEditingController();
  List<dynamic> _presets = [];
  String _preset = 'quick';
  String? _jobId;
  Map<String, dynamic>? _result;

  @override
  void initState() {
    super.initState();
    _loadPresets();
  }

  Future<void> _loadPresets() async {
    try {
      final res = await Api.instance.get('/api/recon/nmap/presets');
      if (!mounted) return;
      setState(() => _presets = res['presets'] ?? []);
    } catch (_) {}
  }

  Future<void> _preview() async {
    try {
      final res = await Api.instance.post('/api/recon/nmap/preview', {
        'target': _target.text.trim(),
        'preset': _preset,
        'extra_args': _extra.text.trim(),
      });
      if (!mounted) return;
      final ok = await CommandPreviewDialog.confirm(
        context,
        title: 'nmap — preset $_preset',
        command: res['command'],
        warning: 'Pastikan target adalah sistem milikmu / ada izinnya.',
      );
      if (ok) _run();
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _run() async {
    try {
      final res = await Api.instance.post('/api/recon/nmap/run', {
        'target': _target.text.trim(),
        'preset': _preset,
        'extra_args': _extra.text.trim(),
      });
      if (!mounted) return;
      setState(() {
        _jobId = res['job']['id'];
        _result = null;
      });
      _pollResult();
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _pollResult() async {
    // simple poll: when job done, fetch result
    for (var i = 0; i < 600; i++) {
      await Future.delayed(const Duration(seconds: 1));
      if (!mounted) return;
      try {
        final job = await Api.instance.get('/api/jobs/$_jobId?with_lines=false');
        if (job['status'] != 'running') {
          if (!mounted) return;
          setState(() => _result = job['result']);
          return;
        }
      } catch (_) {
        return;
      }
    }
  }

  void _snack(String msg) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));

  @override
  Widget build(BuildContext context) {
    final hosts = (_result?['hosts'] as List?) ?? [];
    final surface = (_result?['attack_surface'] as List?) ?? [];
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Recon — Nmap',
              style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(
              flex: 2,
              child: TextField(
                controller: _target,
                decoration:
                    const InputDecoration(labelText: 'Target (IP / CIDR / host)'),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: DropdownButtonFormField<String>(
                value: _preset,
                items: [
                  for (final p in _presets)
                    DropdownMenuItem(
                      value: '${p['id']}',
                      child: Text('${p['id']} — ${p['desc']}',
                          overflow: TextOverflow.ellipsis),
                    ),
                ],
                onChanged: (v) => setState(() => _preset = v ?? 'quick'),
                decoration: const InputDecoration(labelText: 'Preset'),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: TextField(
                controller: _extra,
                decoration: const InputDecoration(
                    labelText: 'Argumen ekstra (opsional)'),
              ),
            ),
            const SizedBox(width: 8),
            FilledButton.icon(
              onPressed: _target.text.trim().isEmpty ? null : _preview,
              icon: const Icon(Icons.play_arrow, size: 18),
              label: const Text('Scan'),
            ),
          ]),
          const SizedBox(height: 12),
          Expanded(
            flex: 3,
            child: TerminalBox(jobId: _jobId),
          ),
          const SizedBox(height: 12),
          if (_result != null)
            Expanded(
              flex: 2,
              child: Card(
                child: ListView(
                  padding: const EdgeInsets.all(12),
                  children: [
                    const Text('Host & Attack Surface',
                        style: TextStyle(fontWeight: FontWeight.bold)),
                    const Divider(),
                    for (final h in hosts)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('${h['ip']}  ${h['hostname'] ?? ''}  ${h['os'] ?? ''}',
                                style: const TextStyle(
                                    fontWeight: FontWeight.w600, fontSize: 13.5)),
                            for (final p in (h['ports'] as List? ?? []))
                              Padding(
                                padding: const EdgeInsets.only(left: 16, top: 2),
                                child: Text(
                                  '${p['port']}/${p['protocol']}  ${p['service']}  ${p['product']}'
                                  '${p['interesting'] == true ? '  ★' : ''}',
                                  style: TextStyle(
                                      fontSize: 12.5,
                                      color: p['interesting'] == true
                                          ? kGreen
                                          : Colors.white70),
                                ),
                              ),
                          ],
                        ),
                      ),
                    if (surface.isNotEmpty) ...[
                      const Divider(),
                      const Text('Saran attack surface:',
                          style: TextStyle(fontWeight: FontWeight.w600)),
                      for (final s in surface)
                        Padding(
                          padding: const EdgeInsets.only(left: 16, top: 4),
                          child: Text('• $s',
                              style: const TextStyle(
                                  fontSize: 12.5, color: kAccent)),
                        ),
                    ],
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}
