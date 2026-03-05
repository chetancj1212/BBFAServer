class ApiConfig {
  // Fix #13: env-driven URL via --dart-define=API_URL=http://localhost:8700
  static const String baseUrl = String.fromEnvironment(
    'API_URL',
    defaultValue: 'https://api.chetancj.in',
  );
  static const String _wsBase = String.fromEnvironment(
    'WS_URL',
    defaultValue: 'wss://api.chetancj.in',
  );

  // Endpoints
  static const String groups = '/attendance/groups';
  static String lookup(String groupId, String enrollment) =>
      '/student/lookup/$groupId/$enrollment';
  static const String registerFace = '/student/register-face';
  static const String verifyAndMark = '/student/verify-and-mark';
  static const String markAttendance = '/student/mark-attendance';
  static const String classStatus = '/class/status';
  static const String classStatusWs = '/class/ws/class-status';
  static const String verifyBle = '/student/verify-ble';
  static const String resolveDevice = '/student/resolve-device';
  static String deviceName(String groupId) => '/student/device-name/$groupId';

  static String url(String path) => '$baseUrl$path';
  static Uri wsUri(String path) => Uri.parse('$_wsBase$path');
  static String wsUrl(String path) => '$_wsBase$path';
}
