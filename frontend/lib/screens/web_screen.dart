import 'package:flutter/material.dart';

import '../services/api.dart';
import '../theme.dart';
import '../widgets/command_preview.dart';
import '../widgets/finding_card.dart';
import '../widgets/terminal_box.dart';

class WebScreen extends StatefulWidget {
  const WebScreen({super.key});

  @override
  State<WebScreen> createState() => _WebScreenState();
}

class _WebScreenState extends State<WebScreen> {
  final _url = TextEditingController(text: 'http://127.0.0.1:5000');
  Map<String, dynamic>? _crawl;
  List<dynamic> _findings = [];
  String? _jobId; // current running job (owasp/sqli/auth)
  String _jobLabel = '';

  Future<void> _runCrawl() async {
    try {
      final res = await Api.instance.post('/api/web/crawl', {
        'url': _url.text.trim(), 'max_pages': 30, 'depth': 2,
      });
      if (!mounted) return;
      setState(() => _crawl = Map<String, dynamic>.from(res));
      _snack('crawl: ${res['pages_count']} halaman, '
          '${res['analysis']['total']} attack point');
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _owasp() async {
    await _launchJob('/api/web/owasp', {
      'url': _url.text.trim(),
      'params_urls': List<String>.from(_crawl?['urls_with_params'] ?? []),
      'forms': List<dynamic>.from(_crawl?['forms'] ?? []),
    }, 'OWASP scan');
  }

  Future<void> _sqli() async {
    final urls = List<String>.from(_crawl?['urls_with_params'] ?? []);
    if (urls.isEmpty) return _snack('tidak ada URL berparameter — crawl dulu');
    final cmd = await Api.instance.post('/api/web/sqlmap/preview',
        {'url': urls.first, 'level': 2, 'risk': 2});
    if (!mounted) return;
    final ok = await CommandPreviewDialog.confirm(
        context, title: 'SQLMap', command: cmd['command'],
        warning: 'SQLMap mengirim payload injection aktif ke target.');
    if (!ok) return;
    final res = await Api.instance.post('/api/web/sqlmap/run',
        {'url': urls.first, 'level': 2, 'risk': 2});
    if (!mounted) return;
    setState(() { _jobId = res['job']['id']; _jobLabel = 'SQLMap'; });
  }

  Future<void> _authBypass() async {
    final loginUrl = await _askLoginUrl();
    if (loginUrl == null) return;
    await _launchJob('/api/web/auth-bypass', {'url': loginUrl}, 'Auth bypass');
  }

  Future<String?> _askLoginUrl() async {
    final ctrl = TextEditingController(text: '${_url.text.trim()}/login');
    final res = await showDialog<String>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: kSurface,
        title: const Text('URL form login'),
        content: TextField(controller: ctrl,
            decoration: const InputDecoration(labelText: 'URL')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Batal')),
          FilledButton(onPressed: () => Navigator.pop(context, ctrl.text.trim()),
              child: const Text('OK')),
        ],
      ),
    );
    return (res == null || res.isEmpty) ? null : res;
  }

  Future<void> _launchJob(String path, Map<String, dynamic> body, String label) async {
    try {
      final res = await Api.instance.post(path, body);
      if (!mounted) return;
      setState(() { _jobId = res['job']['id']; _jobLabel = label; });
      _pollFindings();
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _pollFindings() async {
    for (var i = 0; i < 600; i++) {
      await Future.delayed(const Duration(seconds: 1));
      if (!mounted) return;
      try {
        final job = await Api.instance.get('/api/jobs/$_jobId?with_lines=false');
        if (job['status'] != 'running') {
          final r = job['result'];
          if (!mounted) return;
          setState(() => _findings = r is Map ? (r['findings'] ?? []) : []);
          _snack('$_jobLabel selesai');
          return;
        }
      } catch (_) { return; }
    }
  }

  void _snack(String msg) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));

  @override
  Widget build(BuildContext context) {
    final analysis = _crawl?['analysis'] as Map<String, dynamic>?;
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Web Exploitation',
              style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(
              child: TextField(controller: _url,
                  decoration: const InputDecoration(
                      labelText: 'Base URL target (milikmu / ada izin)')),
            ),
            const SizedBox(width: 8),
            OutlinedButton.icon(onPressed: _runCrawl,
                icon: const Icon(Icons.travel_explore, size: 18),
                label: const Text('Crawl')),
            const SizedBox(width: 8),
            FilledButton.icon(onPressed: _owasp,
                icon: const Icon(Icons.policy, size: 18),
                label: const Text('OWASP Scan')),
            const SizedBox(width: 8),
            OutlinedButton.icon(onPressed: _sqli,
                icon: const Icon(Icons.storage, size: 18),
                label: const Text('SQLMap')),
            const SizedBox(width: 8),
            OutlinedButton.icon(onPressed: _authBypass,
                icon: const Icon(Icons.key_off, size: 18),
                label: const Text('Auth Bypass')),
          ]),
          if (analysis != null) ...[
            const SizedBox(height: 10),
            Wrap(spacing: 8, children: [
              Chip(label: Text('${_crawl!['pages_count']} halaman')),
              Chip(label: Text('${_crawl!['forms'].length} form')),
              Chip(label: Text('${_crawl!['urls_with_params'].length} URL berparam')),
              ...?((analysis['coverage'] as Map<String, dynamic>?)?.entries.map(
                  (e) => Chip(label: Text('${e.key}: ${e.value}')))),
            ]),
          ],
          const SizedBox(height: 10),
          Expanded(
            flex: 3,
            child: _jobId == null
                ? const Center(child: Text('Jalankan scan untuk melihat output.',
                    style: TextStyle(color: kMuted)))
                : Column(children: [
                    if (_jobLabel.isNotEmpty)
                      Align(alignment: Alignment.centerLeft,
                          child: Text(_jobLabel,
                              style: const TextStyle(color: kMuted, fontSize: 12))),
                    Expanded(child: TerminalBox(jobId: _jobId)),
                  ]),
          ),
          const SizedBox(height: 10),
          Expanded(
            flex: 2,
            child: _findings.isEmpty
                ? const SizedBox.shrink()
                : Column(children: [
                    Align(alignment: Alignment.centerLeft,
                        child: Text('Temuan (${_findings.length})',
                            style: const TextStyle(fontWeight: FontWeight.bold))),
                    Expanded(child: ListView(
                      children: [for (final f in _findings)
                        FindingCard(finding: Map<String, dynamic>.from(f))],
                    )),
                  ]),
          ),
        ],
      ),
    );
  }
}
