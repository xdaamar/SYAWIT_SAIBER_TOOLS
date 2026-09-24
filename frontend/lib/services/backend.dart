import 'dart:async';
import 'dart:convert';
import 'dart:io';

/// Spawns and supervises the CTFSuite FastAPI backend.
class BackendService {
  BackendService._();
  static final BackendService instance = BackendService._();

  Process? _proc;
  int port = 8765;
  bool ready = false;
  final _readyCtrl = StreamController<bool>.broadcast();
  Stream<bool> get onReady => _readyCtrl.stream;
  String baseUrl = 'http://127.0.0.1:8765';
  String? lastError;

  Future<void> start() async {
    if (ready) return;
    // pick a free port so multiple instances can coexist
    final server = await ServerSocket.bind('127.0.0.1', 0);
    port = server.port;
    server.close();

    final backendDir = Directory(
        '${Directory.current.path}${Platform.pathSeparator}..${Platform.pathSeparator}backend');
    final venvPy = File('${backendDir.path}${Platform.pathSeparator}'
        '.venv${Platform.pathSeparator}Scripts${Platform.pathSeparator}python.exe');
    final runPy = File('${backendDir.path}${Platform.pathSeparator}run.py');

    final exist = await Future.wait([venvPy.exists(), runPy.exists()]);
    if (!exist.every((e) => e)) {
      lastError = 'Backend belum ada di ${backendDir.path} — jalankan dari root repo.';
      _readyCtrl.add(false);
      return;
    }

    try {
      _proc = await Process.start(
        venvPy.path,
        [runPy.path],
        workingDirectory: backendDir.path,
        environment: {'CTFSUITE_PORT': '$port'},
        mode: ProcessStartMode.detachedWithStdio,
      );
      _proc!.stderr
          .transform(utf8.decoder)
          .transform(const LineSplitter())
          .listen((l) {
        if (l.trim().isNotEmpty) lastError = l.trim();
      });
    } catch (e) {
      lastError = 'Gagal spawn backend: $e';
      _readyCtrl.add(false);
      return;
    }

    baseUrl = 'http://127.0.0.1:$port';
    // poll health up to 20s
    for (var i = 0; i < 40; i++) {
      await Future.delayed(const Duration(milliseconds: 500));
      try {
        final client = HttpClient()..connectionTimeout = const Duration(seconds: 2);
        final req = await client.getUrl(Uri.parse('$baseUrl/api/health'));
        final res = await req.close();
        await res.drain<void>();
        client.close();
        if (res.statusCode == 200) {
          ready = true;
          _readyCtrl.add(true);
          return;
        }
      } catch (_) {/* keep polling */}
    }
    lastError = 'Backend tidak merespon /api/health. $lastError';
    _readyCtrl.add(false);
  }

  void stop() {
    _proc?.kill();
    _proc = null;
    ready = false;
  }
}
