import 'dart:async';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:permission_handler/permission_handler.dart';

enum BleStatus { idle, scanning, found, error }

class BleService {
  static final BleService _instance = BleService._internal();
  factory BleService() => _instance;
  BleService._internal();

  static const Duration _scanTimeout = Duration(seconds: 10);

  /// Vendor ID used by our ESP32 devices for manufacturer data
  static const int _espVendorId = 0xFFFF;

  BleStatus _status = BleStatus.idle;
  String? _error;
  String? _bleToken; // Extracted 8-digit TOTP from manufacturer data
  String? _deviceName; // Discovered ESP device name (tells us which classroom)

  BleStatus get status => _status;
  bool get isFound => _status == BleStatus.found;
  String? get error => _error;
  String? get bleToken => _bleToken;
  String? get deviceName => _deviceName;

  final _statusController = StreamController<BleStatus>.broadcast();
  Stream<BleStatus> get statusStream => _statusController.stream;

  StreamSubscription? _scanSub;

  /// Request all required permissions for BLE scanning
  Future<bool> _requestPermissions() async {
    final statuses = await [
      Permission.bluetoothScan,
      Permission.bluetoothConnect,
      Permission.locationWhenInUse,
    ].request();

    final allGranted = statuses.values.every((s) => s.isGranted || s.isLimited);

    if (!allGranted) {
      _status = BleStatus.error;
      _error = 'Permissions required. Please allow in Settings.';
      _statusController.add(_status);
      return false;
    }

    // Check if Location Services (GPS) are actually enabled
    final isLocationEnabled = await Permission.location.serviceStatus.isEnabled;
    if (!isLocationEnabled) {
      _status = BleStatus.error;
      _error = 'Location services (GPS) are required for scanning. Please turn them ON.';
      _statusController.add(_status);
      return false;
    }

    return true;
  }

  /// Parse manufacturer data from ESP32 advertisement.
  /// Format: [0xFF, 0xFF, byte2, byte3, byte4, byte5]
  /// The 8-digit TOTP is the big-endian uint32 at bytes 2..5.
  String? _extractToken(AdvertisementData adv) {
    try {
      // flutter_blue_plus exposes manufacturer data as Map<int, List<int>>
      final mfr = adv.manufacturerData;
      if (mfr.isEmpty) return null;

      // Vendor ID 0xFFFF — look for it
      List<int>? payload = mfr[0xFFFF];
      if (payload == null && mfr.isNotEmpty) {
        // Fallback: take first available entry
        payload = mfr.values.first;
      }
      if (payload == null || payload.length < 4) return null;

      // The ESP packs: VendorID(2B) + code(4B) in setManufacturerData
      // flutter_blue_plus strips the vendor ID bytes already, giving us
      // [byte2, byte3, byte4, byte5] directly.
      // We try both interpretations:
      List<int> codeBytes;
      if (payload.length >= 6) {
        // Raw with vendor ID prefix still present
        codeBytes = payload.sublist(2, 6);
      } else {
        codeBytes = payload.sublist(0, 4);
      }

      final code =
          ((codeBytes[0] << 24) |
              (codeBytes[1] << 16) |
              (codeBytes[2] << 8) |
              codeBytes[3]) %
          100000000;

      return code.toString().padLeft(8, '0');
    } catch (_) {
      return null;
    }
  }

  /// Scan for a specific ESP32 device by name (resolved from enrollment→group→room).
  /// Extracts the TOTP token from its manufacturer data.
  /// Returns true if the target device is found.
  Future<bool> scan({required String targetDeviceName}) async {
    _status = BleStatus.scanning;
    _bleToken = null;
    _deviceName = null;
    _error = null;
    _statusController.add(_status);

    try {
      final hasPermission = await _requestPermissions();
      if (!hasPermission) return false;

      final adapterState = await FlutterBluePlus.adapterState.first;
      if (adapterState != BluetoothAdapterState.on) {
        _status = BleStatus.error;
        _error = 'Please enable Bluetooth and try again.';
        _statusController.add(_status);
        return false;
      }

      if (FlutterBluePlus.isScanningNow) {
        await FlutterBluePlus.stopScan();
      }

      final completer = Completer<bool>();

      _scanSub = FlutterBluePlus.onScanResults.listen((results) {
        for (ScanResult r in results) {
          final name = r.device.platformName.isNotEmpty
              ? r.device.platformName
              : r.advertisementData.advName;

          if (name == targetDeviceName) {
            final token = _extractToken(r.advertisementData);

            FlutterBluePlus.stopScan();
            _scanSub?.cancel();

            _deviceName = name;
            _bleToken = token;
            _status = BleStatus.found;
            _error = null;
            _statusController.add(_status);

            if (!completer.isCompleted) completer.complete(true);
            return;
          }
        }
      });

      // Start scan (non-blocking)
      FlutterBluePlus.startScan(timeout: _scanTimeout);

      final found = await completer.future.timeout(
        _scanTimeout + const Duration(seconds: 2),
        onTimeout: () => false,
      );

      if (!found) {
        await FlutterBluePlus.stopScan();
        _scanSub?.cancel();
        _status = BleStatus.error;
        _error =
            'Device "$targetDeviceName" not found. Make sure you\'re in the classroom.';
        _statusController.add(_status);
        return false;
      }

      return true;
    } catch (e) {
      await FlutterBluePlus.stopScan();
      _scanSub?.cancel();
      _status = BleStatus.error;
      _error = 'Scan failed. Please try again.';
      _statusController.add(_status);
      return false;
    }
  }

  void reset() {
    _scanSub?.cancel();
    _scanSub = null;
    _bleToken = null;
    _deviceName = null;
    _status = BleStatus.idle;
    _error = null;
    _statusController.add(_status);
  }

  void dispose() {
    _scanSub?.cancel();
    _statusController.close();
  }
}
