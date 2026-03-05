/* Types for BBFA Admin Panel */

export interface Admin {
  id: string;
  unique_id: string;
  name: string;
  created_at: string;
}

export interface Room {
  id: string;
  room_no: string;
  device_name: string; // ESP device e.g. "S3B_106"
  description?: string;
}

export interface ClassInfo {
  group_id: string;
  name: string;
  room_id?: string;
  total_students: number;
  description?: string;
}

export interface Subject {
  id: string;
  group_id: string;
  name: string;
  created_at?: string;
}

export interface StudentRecord {
  person_id: string;
  name: string;
  enrollment_no: string;
  status: "present" | "absent";
  check_in_time?: string;
}

export interface ActiveSession {
  session_id: string;
  group_id: string;
  group_name: string;
  room_no: string;
  device_name: string;
  started_at: string;
  subject_name?: string;
  students: StudentRecord[];
  total_students: number;
  present_count: number;
}

export interface SessionHistory {
  id: string;
  group_id: string;
  group_name: string;
  session_name: string;
  subject_name?: string;
  started_at: string | null;
  ended_at: string | null;
  present_count: number;
  total_members: number;
}
