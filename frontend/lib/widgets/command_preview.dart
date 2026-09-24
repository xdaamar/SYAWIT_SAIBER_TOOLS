import 'package:flutter/material.dart';

import '../theme.dart';

/// Ethics gate: show the exact command/operation, require confirmation.
class CommandPreviewDialog extends StatelessWidget {
  final String title;
  final String command;
  final String? warning;
  const CommandPreviewDialog({
    super.key,
    required this.title,
    required this.command,
    this.warning,
  });

  /// Returns true if the user confirms execution.
  static Future<bool> confirm(BuildContext context,
      {required String title, required String command, String? warning}) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => CommandPreviewDialog(
          title: title, command: command, warning: warning),
    );
    return ok ?? false;
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      backgroundColor: kSurface,
      title: Row(children: const [
        Icon(Icons.gavel, color: kYellow, size: 20),
        SizedBox(width: 8),
        Expanded(child: Text('Preview perintah')),
      ]),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 10),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: const Color(0xFF0A0C10),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: const Color(0xFF30363D)),
            ),
            child: SelectableText(
              command,
              style: const TextStyle(
                  fontFamily: 'Consolas, Courier New, monospace',
                  fontSize: 12.5,
                  color: kGreen),
            ),
          ),
          if (warning != null) ...[
            const SizedBox(height: 10),
            Text(warning!,
                style: const TextStyle(color: kYellow, fontSize: 12.5)),
          ],
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, false),
          child: const Text('Batal'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, true),
          child: const Text('Jalankan'),
        ),
      ],
    );
  }
}
