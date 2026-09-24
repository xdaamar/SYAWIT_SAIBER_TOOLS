import 'package:flutter/material.dart';

import '../services/api.dart';
import '../theme.dart';

class CryptoScreen extends StatefulWidget {
  const CryptoScreen({super.key});

  @override
  State<CryptoScreen> createState() => _CryptoScreenState();
}

class _CryptoScreenState extends State<CryptoScreen>
    with SingleTickerProviderStateMixin {
  late final _tabs = TabController(length: 3, vsync: this);
  final _input = TextEditingController();

  // results
  Map<String, dynamic>? _solve;
  Map<String, dynamic>? _hash;
  List<dynamic> _identify = [];
  Map<String, dynamic>? _crack;
  final _digest = TextEditingController();
  final _n = TextEditingController();
  final _e = TextEditingController();
  final _c = TextEditingController();
  Map<String, dynamic>? _rsa;

  Future<void> _doSolve() async {
    try {
      final res = await Api.instance.post(
          '/api/crypto/solve', {'text': _input.text, 'max_depth': 3});
      if (!mounted) return;
      setState(() => _solve = Map<String, dynamic>.from(res));
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _doHash() async {
    try {
      final res =
          await Api.instance.post('/api/crypto/hash', {'text': _input.text});
      if (!mounted) return;
      setState(() => _hash = Map<String, dynamic>.from(res));
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _doIdentify() async {
    try {
      final res = await Api.instance
          .post('/api/crypto/hash/identify', {'digest': _digest.text.trim()});
      if (!mounted) return;
      setState(() {
        _identify = res['candidates'] ?? [];
        _crack = null;
      });
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _doCrack(String algo) async {
    try {
      final res = await Api.instance.post('/api/crypto/hash/crack',
          {'digest': _digest.text.trim(), 'algo': algo});
      if (!mounted) return;
      setState(() => _crack = Map<String, dynamic>.from(res));
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _doRsa() async {
    try {
      final body = {'n': _n.text.trim(), 'e': _e.text.trim()};
      if (_c.text.trim().isNotEmpty) body['c'] = _c.text.trim();
      final res = await Api.instance.post('/api/crypto/rsa/analyze', body);
      if (!mounted) return;
      setState(() => _rsa = Map<String, dynamic>.from(res));
    } on ApiException catch (e) {
      _snack(e.message);
    } catch (e) {
      _snack('nilai harus angka: $e');
    }
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
          Text('Crypto Solver',
              style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 8),
          TabBar(
            controller: _tabs,
            tabs: const [
              Tab(text: 'Auto-decode'),
              Tab(text: 'Hash'),
              Tab(text: 'RSA'),
            ],
          ),
          Expanded(
            child: TabBarView(
              controller: _tabs,
              children: [_solveTab(), _hashTab(), _rsaTab()],
            ),
          ),
        ],
      ),
    );
  }

  Widget _solveTab() => Column(children: [
        const SizedBox(height: 12),
        TextField(
          controller: _input,
          maxLines: 3,
          decoration: const InputDecoration(
              labelText: 'Ciphertext / encoding apa saja',
              hintText: 'base64, hex, morse, caesar, brainfuck, ...'),
        ),
        const SizedBox(height: 8),
        Wrap(children: [
          FilledButton(onPressed: _doSolve, child: const Text('Decode')),
          const SizedBox(width: 8),
          OutlinedButton(onPressed: _doHash, child: const Text('Hitung semua hash')),
        ]),
        const SizedBox(height: 12),
        Expanded(child: _monoCard(_solve == null
            ? null
            : [for (final c in (_solve!['candidates'] as List? ?? []))
                '${c['method']}  (score ${c['score']})\n${c['preview']}\n'])),
      ]);

  Widget _hashTab() => Column(children: [
        const SizedBox(height: 12),
        TextField(
          controller: _digest,
          decoration: const InputDecoration(
              labelText: 'Hash target (md5/sha1/sha256...)'),
        ),
        const SizedBox(height: 8),
        Wrap(children: [
          FilledButton(onPressed: _doIdentify, child: const Text('Identify')),
          const SizedBox(width: 8),
          for (final a in ['md5', 'sha1', 'sha256'])
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: OutlinedButton(
                  onPressed: () => _doCrack(a), child: Text('Crack $a')),
            ),
        ]),
        const SizedBox(height: 8),
        for (final i in _identify)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 2),
            child: Text('${i['type']} (len ${i['length']}, confidence ${i['confidence']})',
                style: const TextStyle(color: kGreen, fontSize: 13)),
          ),
        if (_crack != null)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Text(
              _crack!['ok'] == true
                  ? 'CRACKED: ${_crack!['cracked']}'
                  : 'gagal: ${_crack!['error']}',
              style: TextStyle(
                  color: _crack!['ok'] == true ? kGreen : kMuted,
                  fontSize: 14, fontWeight: FontWeight.bold),
            ),
          ),
        Expanded(child: _monoCard(_hash == null
            ? null
            : [for (final e in (_hash!['hashes'] as Map).entries)
                '${e.key}:  ${e.value}'])),
      ]);

  Widget _rsaTab() => Column(children: [
        const SizedBox(height: 12),
        Row(children: [
          Expanded(child: TextField(controller: _n,
              decoration: const InputDecoration(labelText: 'n (modulus)'))),
          const SizedBox(width: 8),
          Expanded(child: TextField(controller: _e,
              decoration: const InputDecoration(labelText: 'e'))),
          const SizedBox(width: 8),
          Expanded(child: TextField(controller: _c,
              decoration: const InputDecoration(labelText: 'c (opsional)'))),
          const SizedBox(width: 8),
          FilledButton(onPressed: _doRsa, child: const Text('Analyze')),
        ]),
        const SizedBox(height: 12),
        Expanded(child: _monoCard(_rsa == null
            ? null
            : [_rsa!.entries.map((e) => '${e.key}: ${e.value}').join('\n')])),
      ]);

  Widget _monoCard(List<String>? lines) {
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: const Color(0xFF0A0C10),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFF30363D)),
      ),
      padding: const EdgeInsets.all(10),
      child: lines == null || lines.isEmpty
          ? const Center(
              child: Text('Hasil muncul di sini.', style: TextStyle(color: kMuted)))
          : SingleChildScrollView(
              child: SelectableText(lines.join('\n'),
                  style: const TextStyle(
                      fontFamily: 'Consolas, Courier New, monospace',
                      fontSize: 12.5, color: Colors.white70, height: 1.45))),
    );
  }
}
