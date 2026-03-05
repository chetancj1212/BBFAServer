import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/student.dart';

class StorageService {
  static const String _studentKey = 'student-storage';
  static const String _attendanceMarkedKey = 'attendance-marked';
  static const String _attendanceTimestampKey = 'attendance-timestamp';

  SharedPreferences? _prefs;

  Future<void> _ensureInit() async {
    _prefs ??= await SharedPreferences.getInstance();
  }

  /// Save student data
  Future<void> saveStudent(Student student) async {
    await _ensureInit();
    await _prefs!.setString(_studentKey, jsonEncode(student.toJson()));
  }

  /// Get saved student
  Future<Student?> getStudent() async {
    await _ensureInit();
    final data = _prefs!.getString(_studentKey);
    if (data == null) return null;
    return Student.fromJson(jsonDecode(data));
  }

  /// Clear student data
  Future<void> clearStudent() async {
    await _ensureInit();
    await _prefs!.remove(_studentKey);
    await _prefs!.remove(_attendanceMarkedKey);
    await _prefs!.remove(_attendanceTimestampKey);
  }

  /// Mark attendance
  Future<void> markAttendance(String timestamp) async {
    await _ensureInit();
    await _prefs!.setBool(_attendanceMarkedKey, true);
    await _prefs!.setString(_attendanceTimestampKey, timestamp);
  }

  /// Check if attendance is marked
  Future<bool> isAttendanceMarked() async {
    await _ensureInit();
    return _prefs!.getBool(_attendanceMarkedKey) ?? false;
  }

  /// Get attendance timestamp
  Future<String?> getAttendanceTimestamp() async {
    await _ensureInit();
    return _prefs!.getString(_attendanceTimestampKey);
  }

  /// Reset attendance
  Future<void> resetAttendance() async {
    await _ensureInit();
    await _prefs!.remove(_attendanceMarkedKey);
    await _prefs!.remove(_attendanceTimestampKey);
  }
}
