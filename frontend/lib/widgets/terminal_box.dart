import 'dart:async';

import 'package:flutter/material.dart';

import '../services/api.dart';
import '../theme.dart';

/// Live terminal for a job: fetches backlog, subscribes to WS, auto-scrolls.
class TerminalBox extends StatefulWidget {
  final String? jobId;
  const TerminalBox({super.key, this.jobId});

  @override
  State<TerminalBox> createState() => _TerminalBoxState();
}

class _TerminalBoxState extends State<TerminalBox> {
  final List<Map<String, dynamic>> _lines = [];
  final ScrollController _scroll = ScrollController();
  StreamSubscription<Map<String, dynamic>>? _sub;
  String? _status;
  String? _loadedFor;

  @override
  void initState() {
    super.initState();
    _attach();
  }

  @override
  void didUpdateWidget(covariant TerminalBox old) {
    super.didUpdateWidget(old);
    if (old.jobId != widget.jobId) _attach();
  }

  Future<void> _attach() async {
    _sub?.cancel();
    _lines.clear();
    _status = null;
    final jobId = widget.jobId;
    if (jobId == null) {
      setState(() {});
      return;
    }
    _loadedFor = jobId;
    // backlog + status
    try {
      final job = await Api.instance.get('/api/jobs/$jobId?with_lines=true');
      if (!mounted || _loadedFor != jobId) return;
      setState(() => _status = job['status']);
      for (final l in (job['lines'] as List? ?? [])) {
        _lines.add(Map<String, dynamic>.from(l));
      }
      _jumpBottom();
    } catch (e) {
      _lines.add({'line': '[!] gagal memuat output: $e', 's': 'err'});
    }
    if (mounted) setState(() {});
    // live
    _sub = Api.instance.jobStream(jobId).listen((msg) {
      if (!mounted) return;
      if (msg['event'] == 'end') {
        setState(() => _status = msg['status'] ?? 'done');
        return;
      }
      if (msg.containsKey('line')) {
        setState(() {
          if (_lines.isNotEmpty && _lines.first['i'] == -1) _lines.clear();
          _lines.add(msg);
        });
        _jumpBottom();
      }
    }, onError: (e) {/* stream closed — fine */});
  }

  void _jumpBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(_scroll.position.maxScrollExtent + 80,
            duration: const Duration(milliseconds: 150), curve: Curves.easeOut);
      }
    });
  }

  @override
  void dispose() {
    _sub?.cancel();
    _scroll.dispose();
    super.dispose();
  }

  Color _colorFor(String s) {
    switch (s) {
      case 'err':
        return kRed;
      case 'cmd':
        return kAccent;
      default:
        return Colors.white70;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: const Color(0xFF0A0C10),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFF30363D)),
      ),
      padding: const EdgeInsets.all(10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const Icon(Icons.terminal, size: 16, color: kGreen),
            const SizedBox(width: 6),
            Text('Output', style: Theme.of(context).textTheme.titleMedium),
            const Spacer(),
            if (_status != null)
              Chip(label: Text(_status!), visualDensity: VisualDensity.compact),
          ]),
          const Divider(),
          Expanded(
            child: widget.jobId == null
                ? const Center(
                    child: Text('Belum ada job. Jalankan aksi dulu.',
                        style: TextStyle(color: kMuted)))
                : _lines.isEmpty
                    ? const Center(
                        child: Text('Menunggu output...',
                            style: TextStyle(color: kMuted)))
                    : ListView.builder(
                        controller: _scroll,
                        itemCount: _lines.length,
                        itemBuilder: (_, i) {
                          final l = _lines[i];
                          final stream = (l['s'] ?? 'out').toString();
                          return Padding(
                            padding: const EdgeInsets.symmetric(vertical: 1),
                            child: Text(
                              '${l['line']}',
                              style: TextStyle(
                                fontFamily: 'Consolas, Courier New, monospace',
                                fontSize: 12.5,
                                color: _colorFor(stream),
                              ),
                            ),
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }
}
