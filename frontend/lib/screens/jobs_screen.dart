import 'package:flutter/material.dart';

import '../services/api.dart';
import '../theme.dart';
import '../widgets/terminal_box.dart';

class JobsScreen extends StatefulWidget {
  const JobsScreen({super.key});

  @override
  State<JobsScreen> createState() => _JobsScreenState();
}

class _JobsScreenState extends State<JobsScreen> {
  List<dynamic> _jobs = [];
  String? _selected;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final res = await Api.instance.get('/api/jobs');
      if (!mounted) return;
      setState(() => _jobs = res['jobs'] ?? []);
    } catch (_) {}
  }

  Future<void> _cancel(String id) async {
    try {
      await Api.instance.post('/api/jobs/$id/cancel');
      _load();
    } catch (e) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('cancel gagal: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Text('Jobs', style: Theme.of(context).textTheme.headlineSmall),
            const Spacer(),
            IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
          ]),
          const SizedBox(height: 8),
          Expanded(
            flex: 2,
            child: Card(
              child: _jobs.isEmpty
                  ? const Center(
                      child: Text('Belum ada job.',
                          style: TextStyle(color: kMuted)))
                  : ListView.separated(
                      itemCount: _jobs.length,
                      separatorBuilder: (_, __) => const Divider(height: 1),
                      itemBuilder: (_, i) {
                        final j = _jobs[i];
                        final st = '${j['status']}';
                        return ListTile(
                          dense: true,
                          selected: _selected == j['id'],
                          leading: Icon(Icons.circle,
                              size: 12, color: statusColor(st)),
                          title: Text('${j['title']}',
                              style: const TextStyle(fontSize: 13.5)),
                          subtitle: Text(
                              '${j['kind']} · ${j['created_at'] != null ? DateTime.fromMillisecondsSinceEpoch((j['created_at'] * 1000).toInt()).toString().substring(5, 19) : ''}',
                              style: const TextStyle(fontSize: 11.5)),
                          trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                            Text(st,
                                style: TextStyle(
                                    fontSize: 12, color: statusColor(st))),
                            const SizedBox(width: 8),
                            if (st == 'running')
                              IconButton(
                                  tooltip: 'Batalkan',
                                  onPressed: () => _cancel('${j['id']}'),
                                  icon: const Icon(Icons.stop,
                                      size: 18, color: kRed)),
                          ]),
                          onTap: () =>
                              setState(() => _selected = '${j['id']}'),
                        );
                      },
                    ),
            ),
          ),
          const SizedBox(height: 10),
          Expanded(flex: 3, child: TerminalBox(jobId: _selected)),
        ],
      ),
    );
  }
}
