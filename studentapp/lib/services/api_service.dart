import 'package:dio/dio.dart';
import '../config/api_config.dart';
import '../models/group.dart';
import '../models/class_status.dart';

class ApiService {
  late final Dio _dio;

  ApiService() {
    _dio = Dio(
      BaseOptions(
        baseUrl: ApiConfig.baseUrl,
        connectTimeout: const Duration(seconds: 60),
        receiveTimeout: const Duration(seconds: 60),
        headers: {'Content-Type': 'application/json'},
      ),
    );
  }

  /// Extract meaningful error from DioException
  String _extractError(dynamic e) {
    if (e is DioException && e.response != null) {
      final data = e.response!.data;
      if (data is Map) {
        return data['detail'] ??
            data['message'] ??
            'Request failed (${e.response!.statusCode})';
      }
      return 'Server error (${e.response!.statusCode})';
    }
    return 'Network error. Check your connection.';
  }

  /// Fetch available groups
  Future<List<Group>> getGroups() async {
    final response = await _dio.get(ApiConfig.groups);
    final data = response.data;
    final list = data is List ? data : (data['groups'] ?? []);
    return (list as List).map((e) => Group.fromJson(e)).toList();
  }

  /// Lookup student
  Future<Map<String, dynamic>> lookupStudent(
    String groupId,
    String enrollmentNo,
  ) async {
    try {
      final response = await _dio.get(ApiConfig.lookup(groupId, enrollmentNo));
      return response.data;
    } on DioException catch (e) {
      throw Exception(_extractError(e));
    }
  }

  /// Register face
  Future<Map<String, dynamic>> registerFace({
    required String enrollmentNo,
    required String groupId,
    required String imageBase64,
  }) async {
    try {
      final response = await _dio.post(
        ApiConfig.registerFace,
        data: {
          'enrollment_no': enrollmentNo,
          'group_id': groupId,
          'image': imageBase64,
        },
      );
      return response.data;
    } on DioException catch (e) {
      throw Exception(_extractError(e));
    }
  }

  /// Verify and mark attendance — sends BLE token for server-side validation
  Future<Map<String, dynamic>> verifyAndMark({
    required String sessionId,
    required String groupId,
    required String imageBase64,
    required String bleToken,
    required String deviceName,
  }) async {
    try {
      final response = await _dio.post(
        ApiConfig.verifyAndMark,
        data: {
          'session_id': sessionId,
          'group_id': groupId,
          'image': imageBase64,
          'ble_token': bleToken,
          'device_name': deviceName,
        },
      );
      return response.data;
    } on DioException catch (e) {
      throw Exception(_extractError(e));
    }
  }

  /// Get class status via REST
  Future<ClassStatusData> getClassStatus() async {
    final response = await _dio.get(ApiConfig.classStatus);
    return ClassStatusData.fromJson(response.data);
  }

  /// Verify BLE TOTP token with backend and resolve active class for this device.
  /// Returns the full response: {valid: bool, active_class: {...} | null}
  Future<Map<String, dynamic>> verifyBleToken(
    String token, {
    required String deviceName,
  }) async {
    try {
      final response = await _dio.post(
        ApiConfig.verifyBle,
        data: {'token': token, 'device_name': deviceName},
      );
      return response.data as Map<String, dynamic>;
    } on DioException catch (e) {
      if (e.response != null &&
          (e.response!.statusCode == 400 || e.response!.statusCode == 422)) {
        return {'valid': false, 'active_class': null};
      }
      throw Exception(_extractError(e));
    }
  }

  /// Fetch device name for a group (Fix #4)
  Future<String> getDeviceName(String groupId) async {
    try {
      final response = await _dio.get(ApiConfig.deviceName(groupId));
      final name = response.data['device_name'];
      if (name == null || (name as String).isEmpty) {
        throw Exception('No device configured for this class. Ask admin to link a room.');
      }
      return name;
    } on DioException catch (e) {
      throw Exception(_extractError(e));
    }
  }

  /// Resolve which BLE device to scan for + active class info, given enrollment number.
  /// Returns {found, student, device_name, active_class} or throws.
  Future<Map<String, dynamic>> resolveDevice(String enrollmentNo) async {
    try {
      final response = await _dio.post(
        ApiConfig.resolveDevice,
        data: {'enrollment_no': enrollmentNo},
      );
      return response.data as Map<String, dynamic>;
    } on DioException catch (e) {
      throw Exception(_extractError(e));
    }
  }
}
