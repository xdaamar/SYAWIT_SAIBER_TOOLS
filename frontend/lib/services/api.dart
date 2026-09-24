import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'backend.dart';

/// Minimal JSON API client on top of dart:io (no external packages).
class Api {
  static final Api instance = Api._();
  Api._();

  HttpClient? _client;
  HttpClient get client {
    _client ??= HttpClient()..connectionTimeout = const Duration(seconds: 15);
    return _client!;
  }

  Uri _u(String path, [Map<String, String>? q]) => Uri.parse(
      '${BackendService.instance.baseUrl}$path')
      .replace(queryParameters: q);

  Future<dynamic> get(String path, [Map<String, String>? q]) async {
    final req = await client.getUrl(_u(path, q));
    req.headers.contentType = ContentType.json;
    final res = await req.close();
    final body = await res.transform(utf8.decoder).join();
    return _decode(body, res.statusCode);
  }

  Future<dynamic> post(String path, [dynamic json, Map<String, String>? q]) async {
    final req = await client.postUrl(_u(path, q));
    req.headers.contentType = ContentType.json;
    if (json != null) req.write(jsonEncode(json));
    final res = await req.close();
    final body = await res.transform(utf8.decoder).join();
    return _decode(body, res.statusCode);
  }

  Future<dynamic> put(String path, [dynamic json]) async {
    final req = await client.openUrl('PUT', _u(path));
    req.headers.contentType = ContentType.json;
    if (json != null) req.write(jsonEncode(json));
    final res = await req.close();
    final body = await res.transform(utf8.decoder).join();
    return _decode(body, res.statusCode);
  }

  dynamic _decode(String body, int status) {
    dynamic data;
    try {
      data = body.isEmpty ? {} : jsonDecode(body);
    } catch (_) {
      data = {'raw': body};
    }
    if (status >= 400) {
      throw ApiException(status, data is Map ? (data['detail']?.toString() ?? 'HTTP $status') : 'HTTP $status');
    }
    return data;
  }

  /// Stream job lines via /api/jobs/{id}/ws. Each message is a decoded map.
  Stream<Map<String, dynamic>> jobStream(String jobId) => _ws('/api/jobs/$jobId/ws');

  /// Stream setup events via /api/setup/events.
  Stream<Map<String, dynamic>> setupEvents() => _ws('/api/setup/events');

  Stream<Map<String, dynamic>> _ws(String path) async* {
    final ws = await WebSocket.connect(
        'ws://127.0.0.1:${BackendService.instance.port}$path');
    try {
      await for (final msg in ws) {
        if (msg is String) {
          try {
            yield jsonDecode(msg) as Map<String, dynamic>;
          } catch (_) {/* ignore malformed */}
        }
      }
    } finally {
      await ws.close().catchError((_) {});
    }
  }
}

class ApiException implements Exception {
  final int status;
  final String message;
  ApiException(this.status, this.message);
  @override
  String toString() => message;
}
