import 'package:flutter/material.dart';

import '../theme.dart';

class FindingCard extends StatelessWidget {
  final Map<String, dynamic> finding;
  const FindingCard({super.key, required this.finding});

  @override
  Widget build(BuildContext context) {
    final sev = (finding['severity'] ?? 'info').toString();
    final color = sevColor(sev);
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
        iconColor: kMuted,
        leading: Chip(
          backgroundColor: color.withOpacity(.15),
          label: Text(sev.toUpperCase(),
              style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.bold)),
          visualDensity: VisualDensity.compact,
          padding: EdgeInsets.zero,
        ),
        title: Text('${finding['title'] ?? '-'}',
            style: const TextStyle(fontSize: 14, color: Colors.white)),
        subtitle: Text(
          '${finding['owasp'] ?? finding['module'] ?? ''} ${finding['url'] ?? ''}'.trim(),
          style: const TextStyle(fontSize: 12, color: kMuted),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
        children: [
          if ((finding['evidence'] ?? '').toString().isNotEmpty) ...[
            Align(
              alignment: Alignment.centerLeft,
              child: Text('Bukti:', style: TextStyle(color: kMuted, fontSize: 12)),
            ),
            Container(
              width: double.infinity,
              margin: const EdgeInsets.only(top: 4),
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: const Color(0xFF0A0C10),
                borderRadius: BorderRadius.circular(6),
              ),
              child: SelectableText('${finding['evidence']}',
                  style: const TextStyle(
                      fontFamily: 'Consolas, Courier New, monospace',
                      fontSize: 12, color: kAccent)),
            ),
          ],
          if ((finding['recommendation'] ?? '').toString().isNotEmpty) ...[
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerLeft,
              child: Text('Rekomendasi: ${finding['recommendation']}',
                  style: const TextStyle(fontSize: 12.5, color: Colors.white70)),
            ),
          ],
        ],
      ),
      ),
    );
  }
}
