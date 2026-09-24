import 'package:flutter/material.dart';

import '../services/api.dart';
import '../theme.dart';
import '../widgets/command_preview.dart';

class PwnScreen extends StatefulWidget {
  const PwnScreen({super.key});

  @override
  State<PwnScreen> createState() => _PwnScreenState();
}

class _PwnScreenState extends State<PwnScreen> {
  final _exe = TextEditingController();
  final _crash = TextEditingController();
  Map<String, dynamic>? _analysis;
  String? _pattern;
  int? _offset;

  String _kind = 'bof';
  final _ret = TextEditingController(text: '0x40123a');
  Map<String, dynamic>? _exploit;

  Future<void> _analyze() async {
    try {
      final res = await Api.instance
          .post('/api/pwn/analyze', {'path': _exe.text.trim()});
      if (!mounted) return;
      setState(() => _analysis = Map<String, dynamic>.from(res));
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _genPattern() async {
    try {
      final res = await Api.instance.get('/api/pwn/pattern?length=300');
      if (!mounted) return;
      setState(() => _pattern = res['pattern']);
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _findOffset() async {
    try {
      final res = await Api.instance
          .post('/api/pwn/offset', {'value': _crash.text.trim()});
      if (!mounted) return;
      setState(() => _offset = res['offset']);
      if (_offset == null) _snack('${res['hint']}');
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _buildExploit() async {
    try {
      final res = await Api.instance.post('/api/pwn/exploit', {
        'kind': _kind,
        'exe_path': _exe.text.trim(),
        'offset': _offset ?? 0,
        'ret_addr': _ret.text.trim(),
        'save': true,
      });
      if (!mounted) return;
      final ok = await CommandPreviewDialog.confirm(context,
          title: 'Generate skrip exploit (${res['filename']})',
          command: res['note'] ?? '',
          warning: 'Skeleton — sesuaikan sebelum dipakai.');
      if (!ok) return;
      setState(() => _exploit = Map<String, dynamic>.from(res));
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  void _snack(String msg) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));

  @override
  Widget build(BuildContext context) {
    final prot = _analysis?['protections'] as Map<String, dynamic>?;
    return Padding(
      padding: const EdgeInsets.all(16),
      child: ListView(
        children: [
          Text('Binary Exploitation',
              style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(child: TextField(controller: _exe,
                decoration: const InputDecoration(
                    labelText: 'Path binary (ELF/PE), mis. C:\\lab\\vuln.exe'))),
            const SizedBox(width: 8),
            FilledButton(onPressed: _analyze, child: const Text('Analyze')),
          ]),
          if (_analysis != null) ...[
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('${_analysis!['format']} · ${_analysis!['machine']} · '
                      '${_analysis!['elf_type'] ?? ''} entry=${_analysis!['entry'] ?? '-'}',
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13.5)),
                  const SizedBox(height: 6),
                  if (prot != null)
                    Wrap(spacing: 8, children: [
                      Chip(label: Text('PIE: ${prot['pie']}')),
                      Chip(label: Text('NX: ${prot['nx']}')),
                      Chip(label: Text('Canary: ${prot['canary']}')),
                    ]),
                  const SizedBox(height: 6),
                  Text('Saran: ${_analysis!['suggestion']}',
                      style: const TextStyle(color: kGreen, fontSize: 13)),
                  if ((_analysis!['interesting_strings'] as List?)?.isNotEmpty == true) ...[
                    const SizedBox(height: 8),
                    const Text('String menarik:', style: TextStyle(color: kMuted, fontSize: 12)),
                    for (final s in (_analysis!['interesting_strings'] as List).take(10))
                      Text('  $s', style: const TextStyle(
                          fontFamily: 'Consolas, Courier New, monospace',
                          fontSize: 12, color: kAccent)),
                  ],
                ]),
              ),
            ),
          ],
          const Divider(height: 32),
          const Text('Cyclic pattern & offset',
              style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Row(children: [
            FilledButton.tonal(onPressed: _genPattern,
                child: const Text('Generate pattern (300)')),
            const SizedBox(width: 8),
            Expanded(child: TextField(controller: _crash,
                decoration: const InputDecoration(
                    labelText: 'Nilai crash (4/8 ascii atau 0x...)'))),
            const SizedBox(width: 8),
            FilledButton(onPressed: _findOffset, child: const Text('Cari offset')),
          ]),
          if (_pattern != null)
            Container(
              margin: const EdgeInsets.only(top: 8),
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: const Color(0xFF0A0C10),
                borderRadius: BorderRadius.circular(6),
              ),
              child: SelectableText(_pattern!,
                  style: const TextStyle(
                      fontFamily: 'Consolas, Courier New, monospace',
                      fontSize: 12, color: Colors.white70)),
            ),
          if (_offset != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text('OFFSET = $_offset',
                  style: const TextStyle(color: kGreen, fontSize: 16,
                      fontWeight: FontWeight.bold)),
            ),
          const Divider(height: 32),
          const Text('Exploit builder',
              style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Row(children: [
            DropdownButton<String>(
              value: _kind,
              items: const [
                DropdownMenuItem(value: 'bof', child: Text('bof / ret2win')),
                DropdownMenuItem(value: 'ret2libc', child: Text('ret2libc')),
                DropdownMenuItem(value: 'fmtstr', child: Text('format string')),
                DropdownMenuItem(value: 'shellcode', child: Text('shellcode')),
              ],
              onChanged: (v) => setState(() => _kind = v ?? 'bof'),
            ),
            const SizedBox(width: 8),
            if (_kind == 'bof' || _kind == 'shellcode')
              SizedBox(width: 160, child: TextField(controller: _ret,
                  decoration: const InputDecoration(labelText: 'ret addr'))),
            const SizedBox(width: 8),
            FilledButton(onPressed: _buildExploit,
                child: const Text('Generate skrip')),
          ]),
          if (_exploit != null) ...[
            const SizedBox(height: 8),
            Text('Disimpan: ${_exploit!['saved_to'] ?? '-'}',
                style: const TextStyle(color: kMuted, fontSize: 12)),
            const SizedBox(height: 6),
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: const Color(0xFF0A0C10),
                borderRadius: BorderRadius.circular(6),
              ),
              child: SelectableText('${_exploit!['script']}',
                  style: const TextStyle(
                      fontFamily: 'Consolas, Courier New, monospace',
                      fontSize: 11.5, color: Colors.white70, height: 1.35)),
            ),
          ],
        ],
      ),
    );
  }
}
