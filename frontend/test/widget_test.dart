import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:syawit_saiber_tools/main.dart';

void main() {
  testWidgets('App boots to boot-gate widget', (tester) async {
    await tester.pumpWidget(const SyawitSaiberToolsApp());
    // BootGate shows a loading indicator while the backend starts.
    expect(find.byType(MaterialApp), findsOneWidget);
  });
}
