enum ClassStatusType { waiting, active, ended, unknown }

class ClassStatusData {
  final ClassStatusType status;
  final String? sessionId;
  final String? groupId;
  final String? startedAt;
  final String? message;
  final String? subjectName;
  final bool enableLiveness;

  ClassStatusData({
    required this.status,
    this.sessionId,
    this.groupId,
    this.startedAt,
    this.message,
    this.subjectName,
    this.enableLiveness = true,
  });

  factory ClassStatusData.fromJson(Map<String, dynamic> json) {
    return ClassStatusData(
      status: _parseStatus(json['status'] as String?),
      sessionId: json['sessionId'] as String?,
      groupId: json['groupId'] as String?,
      startedAt: json['startedAt'] as String?,
      message: json['message'] as String?,
      subjectName: json['subjectName'] as String?,
      enableLiveness: json['enableLiveness'] as bool? ?? true,
    );
  }

  static ClassStatusType _parseStatus(String? s) {
    switch (s) {
      case 'waiting':
        return ClassStatusType.waiting;
      case 'active':
        return ClassStatusType.active;
      case 'ended':
        return ClassStatusType.ended;
      default:
        return ClassStatusType.unknown;
    }
  }
}
