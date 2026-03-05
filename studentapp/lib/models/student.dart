class Student {
  final String id;
  final String name;
  final String enrollmentNo;
  final String groupId;
  final String? groupName;

  Student({
    required this.id,
    required this.name,
    required this.enrollmentNo,
    required this.groupId,
    this.groupName,
  });

  factory Student.fromJson(Map<String, dynamic> json) {
    return Student(
      id: json['id'] ?? '',
      name: json['name'] ?? '',
      enrollmentNo: json['enrollment_no'] ?? '',
      groupId: json['group_id'] ?? '',
      groupName: json['group_name'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'enrollment_no': enrollmentNo,
      'group_id': groupId,
      'group_name': groupName,
    };
  }
}

class StudentLookup {
  final String id;
  final String name;
  final String enrollmentNo;
  final bool? hasFace;

  StudentLookup({
    required this.id,
    required this.name,
    required this.enrollmentNo,
    this.hasFace,
  });

  factory StudentLookup.fromJson(Map<String, dynamic> json) {
    return StudentLookup(
      id: json['id'] ?? '',
      name: json['name'] ?? '',
      enrollmentNo: json['enrollment_no'] ?? '',
      hasFace: json['has_face'],
    );
  }
}
