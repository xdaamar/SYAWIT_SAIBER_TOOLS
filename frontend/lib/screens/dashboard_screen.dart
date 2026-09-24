import 'package:flutter/material.dart';

import '../services/api.dart';
import '../theme.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  Map<String, dynamic>? _status;
  List<dynamic> _jobs = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final status = await Api.instance.get('/api/setup/status');
      final jobs = await Api.instance.get('/api/jobs');
      if (!mounted) return;
      setState(() {
        _status = Map<String, dynamic>.from(status);
        _jobs = jobs['jobs'] ?? [];
      });
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final components = (_status?['components'] as List?) ?? [];
    final okCount = components.where((c) => c['status'] == 'ok').length;
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(children: [
            Text('Dashboard',
                style: Theme.of(context).textTheme.headlineSmall),
          ]),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(children: [
                Icon(
                  _status?['ready'] == true ? Icons.verified : Icons.warning_amber,
                  color: _status?['ready'] == true ? kGreen : kYellow,
                  size: 36,
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _status?['ready'] == true
                            ? 'Environment siap'
                            : 'Environment belum siap',
                        style: const TextStyle(
                            fontSize: 16, fontWeight: FontWeight.bold),
                      ),
                      Text('$okCount/${components.length} komponen OK',
                          style: const TextStyle(color: kMuted, fontSize: 13)),
                    ],
                  ),
                ),
                FilledButton(
                  onPressed: () => _go('/setup'),
                  child: const Text('Buka Setup'),
                ),
              ]),
            ),
          ),
          const SizedBox(height: 16),
          const Text('Modul',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          GridView.count(
            crossAxisCount: 4,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            childAspectRatio: 2.4,
            mainAxisSpacing: 10,
            crossAxisSpacing: 10,
            children: [
              _module(Icons.radar, 'Recon', 'nmap scan + attack surface', '/recon'),
              _module(Icons.language, 'Web', 'crawler, OWASP, sqlmap, auth', '/web'),
              _module(Icons.enhanced_encryption_outlined, 'Crypto',
                  'decode, hash, RSA', '/crypto'),
              _module(Icons.memory_outlined, 'Pwn', 'analyzer + exploit builder',
                  '/pwn'),
              _module(Icons.terminal, 'Shells', 'payload, webshell, listener',
                  '/shells'),
              _module(Icons.list_alt, 'Jobs', 'riwayat & output live', '/jobs'),
            ],
          ),
          const SizedBox(height: 16),
          Row(children: [
            const Text('Job terakhir',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            const Spacer(),
            TextButton(onPressed: _load, child: const Text('Refresh')),
          ]),
          if (_jobs.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 24),
              child: Center(
                  child: Text('Belum ada job dijalankan.',
                      style: TextStyle(color: kMuted))),
            )
          else
            ..._jobs.take(6).map((j) => Card(
                  child: ListTile(
                    dense: true,
                    leading: Icon(Icons.circle,
                        size: 12,
                        color: statusColor('${j['status']}')),
                    title: Text('${j['title']}',
                        style: const TextStyle(fontSize: 13.5)),
                    subtitle: Text('kind: ${j['kind']} · ${j['line_count']} baris',
                        style: const TextStyle(fontSize: 12)),
                    trailing: Text('${j['status']}',
                        style: TextStyle(fontSize: 12, color: statusColor('${j['status']}'))),
                  ),
                )),
        ],
      ),
    );
  }

  Widget _module(IconData icon, String title, String subtitle, String route) {
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => _go(route),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Row(children: [
                Icon(icon, size: 18, color: kGreen),
                const SizedBox(width: 8),
                Text(title,
                    style: const TextStyle(
                        fontWeight: FontWeight.bold, fontSize: 14)),
              ]),
              const SizedBox(height: 4),
              Text(subtitle,
                  style: const TextStyle(fontSize: 11.5, color: kMuted),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis),
            ],
          ),
        ),
      ),
    );
  }

  void _go(String route) => Navigator.pushNamed(context, route);
}
