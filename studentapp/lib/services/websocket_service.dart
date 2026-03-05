import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../config/api_config.dart';
import '../models/class_status.dart';

class WebSocketService {
  WebSocketChannel? _channel;
  Timer? _reconnectTimer;
  int _reconnectAttempts = 0;
  static const int _maxReconnectAttempts = 10;
  static const Duration _reconnectDelay = Duration(seconds: 3);

  bool _isConnected = false;
  bool get isConnected => _isConnected;

  final _statusController = StreamController<ClassStatusData>.broadcast();
  Stream<ClassStatusData> get statusStream => _statusController.stream;

  final _connectionController = StreamController<bool>.broadcast();
  Stream<bool> get connectionStream => _connectionController.stream;

  /// NOTE: The server-side WebSocket endpoint is currently a no-op
  /// (broadcast_class_status is a pass-through). This service will fail to
  /// connect and exhaust reconnect attempts silently. The student app should
  /// rely on REST polling via ApiService.getClassStatus() instead.
  /// TODO: Re-enable once a real WebSocket endpoint is implemented on the server.
  Future<void> connect() async {
    _cleanup();
    try {
      final wsUri = ApiConfig.wsUri(ApiConfig.classStatusWs);
      _channel = WebSocketChannel.connect(wsUri);

      // REQUIRED in web_socket_channel v3: await ready before using the channel.
      // This is where connection failures surface as exceptions.
      await _channel!.ready;

      _channel!.stream.listen(
        (data) {
          if (!_isConnected) {
            _isConnected = true;
            _connectionController.add(true);
            _reconnectAttempts = 0;
          }
          try {
            final json = jsonDecode(data as String);
            _statusController.add(ClassStatusData.fromJson(json));
          } catch (_) {}
        },
        onError: (_) {
          _isConnected = false;
          _connectionController.add(false);
          _scheduleReconnect();
        },
        onDone: () {
          _isConnected = false;
          _connectionController.add(false);
          _scheduleReconnect();
        },
      );
    } catch (e) {
      // Covers WebSocketChannelException, SocketException, etc.
      _isConnected = false;
      _connectionController.add(false);
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (_reconnectAttempts >= _maxReconnectAttempts) return;
    _reconnectAttempts++;
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(_reconnectDelay, connect);
  }

  void _cleanup() {
    _reconnectTimer?.cancel();
    _channel?.sink.close();
    _channel = null;
  }

  void disconnect() {
    _reconnectAttempts = _maxReconnectAttempts; // prevent reconnect
    _cleanup();
    _isConnected = false;
    _connectionController.add(false);
  }

  void dispose() {
    disconnect();
    _statusController.close();
    _connectionController.close();
  }
}
