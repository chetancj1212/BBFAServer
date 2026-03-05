/// Active class/lecture info resolved from the BLE device name.
class ActiveClassInfo {
  final String sessionId;
  final String groupId;
  final String className;
  final String? subjectName;
  final String? roomNo;
  final String? startedAt;

  ActiveClassInfo({
    required this.sessionId,
    required this.groupId,
    required this.className,
    this.subjectName,
    this.roomNo,
    this.startedAt,
  });

  factory ActiveClassInfo.fromJson(Map<String, dynamic> json) {
    return ActiveClassInfo(
      sessionId: json['session_id'] as String,
      groupId: json['group_id'] as String,
      className: json['class_name'] as String? ?? '',
      subjectName: json['subject_name'] as String?,
      roomNo: json['room_no'] as String?,
      startedAt: json['started_at'] as String?,
    );
  }

  /// Display label: subject name if available, otherwise class name
  String get displayName => subjectName ?? className;

  /// Combined display: "CLASS - SUBJECT" or just "CLASS"
  String get fullDisplayName =>
      subjectName != null ? '$className - $subjectName' : className;
}
