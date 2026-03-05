/**
 * API service for BBFA Admin Panel
 * All calls go through Next.js rewrite → FastAPI backend at :8700
 */

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "https://api.chetancj.in";

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": "dev-key-change-me",
      ...(opts?.headers as Record<string, string>),
    },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

/* ── Auth ── */
export async function adminLogin(uniqueId: string, password: string) {
  return request<{
    success: boolean;
    admin: { id: string; unique_id: string; name: string; created_at: string };
  }>("/panel/login", {
    method: "POST",
    body: JSON.stringify({ unique_id: uniqueId, password }),
  });
}

/* ── Rooms ── */
export async function getRooms() {
  return request<{
    rooms: Array<{
      id: string;
      room_no: string;
      device_name: string;
      description?: string;
    }>;
  }>("/panel/rooms");
}

export async function createRoom(
  room_no: string,
  device_name: string,
  description?: string,
) {
  return request<{ success: boolean; room: any }>("/panel/rooms", {
    method: "POST",
    body: JSON.stringify({ room_no, device_name, description }),
  });
}

/* ── Classes (groups) ── */
export async function getClasses() {
  return request<any[]>("/attendance/groups");
}

export async function getClassMembers(groupId: string) {
  return request<any[]>(`/attendance/groups/${groupId}/members`);
}

/* ── Sessions ── */
export async function createAndStartSession(groupId: string, subjectId?: string) {
  return request<{ success: boolean; session_id: string; started_at: string; subject_name?: string }>(
    `/class/quick-start/${groupId}`,
    {
      method: "POST",
      body: JSON.stringify({ subject_id: subjectId || null }),
    },
  );
}

export async function endSession(sessionId: string) {
  return request<{
    success: boolean;
    ended_at: string;
    archived_records: number;
  }>(`/class/sessions/${sessionId}/end`, { method: "POST" });
}

export async function getActiveSessions() {
  return request<{ sessions: any[] }>("/class/sessions");
}

export async function getClassStatus() {
  return request<any>("/class/status");
}

/* ── Live records ── */
export async function getAttendanceRecords(
  groupId: string,
  startDate?: string,
) {
  let url = `/attendance/records?group_id=${groupId}&limit=1000`;
  if (startDate) url += `&start_date=${encodeURIComponent(startDate)}`;
  return request<any[]>(url);
}

/* ── Manual attendance ── */
export async function markManualAttendance(personId: string) {
  return request<any>("/attendance/records", {
    method: "POST",
    body: JSON.stringify({
      person_id: personId,
      confidence: 1.0,
      is_manual: true,
      notes: "Marked by admin via panel",
    }),
  });
}

/* ── History ── */
export async function getSessionHistory(groupId?: string, limit = 50) {
  let url = `/class/history?limit=${limit}`;
  if (groupId) url += `&group_id=${groupId}`;
  return request<{ sessions: any[] }>(url);
}

export async function getHistoryDetail(sessionId: string) {
  return request<{ records: any[] }>(`/class/history/${sessionId}`);
}

export async function deleteHistorySession(sessionId: string) {
  return request<{ success: boolean }>(`/class/history/${sessionId}`, {
    method: "DELETE",
  });
}

/* ── Room delete ── */
export async function deleteRoom(roomId: string) {
  return request<{ success: boolean }>(`/panel/rooms/${roomId}`, {
    method: "DELETE",
  });
}

/* ── Group (Class) CRUD ── */
export async function createClass(
  name: string,
  description?: string,
  roomId?: string,
) {
  return request<any>("/attendance/groups", {
    method: "POST",
    body: JSON.stringify({
      name,
      description: description || "",
      room_id: roomId || null,
    }),
  });
}

export async function updateClass(
  groupId: string,
  updates: { name?: string; description?: string; room_id?: string | null },
) {
  return request<any>(`/attendance/groups/${groupId}`, {
    method: "PUT",
    body: JSON.stringify(updates),
  });
}

export async function deleteClass(groupId: string) {
  return request<{ success: boolean }>(`/attendance/groups/${groupId}`, {
    method: "DELETE",
  });
}

/* ── Member CRUD (admin panel — read-only, assigning only) ── */
// Note: addMember, addMembersBulk, deleteMember, deleteClass removed —
// these operations are now super-admin-only via the front/ panel.

/* ── Subjects ── */
export async function getSubjects(groupId: string) {
  return request<Array<{ id: string; group_id: string; name: string; created_at?: string }>>(
    `/attendance/subjects/${groupId}`,
  );
}

export async function createSubject(groupId: string, name: string) {
  return request<{ success: boolean; subject: any }>(
    `/attendance/subjects?group_id=${encodeURIComponent(groupId)}&name=${encodeURIComponent(name)}`,
    { method: "POST" },
  );
}

export async function deleteSubject(subjectId: string) {
  return request<{ success: boolean }>(`/attendance/subjects/${subjectId}`, {
    method: "DELETE",
  });
}

export async function assignSubjectMembers(subject_id: string, person_ids: string[]) {
  return request<{ success: boolean; count: number }>(
    `/attendance/subjects/${subject_id}/members`,
    {
      method: "POST",
      body: JSON.stringify({ person_ids }),
    },
  );
}

export async function getSubjectMembers(subject_id: string) {
  return request<{ results: any[]; count: number }>(
    `/attendance/subjects/${subject_id}/members`,
  );
}

export async function removeSubjectMember(subject_id: string, person_id: string) {
  return request<{ success: boolean; message: string }>(
    `/attendance/subjects/${subject_id}/members/${person_id}`,
    { method: "DELETE" },
  );
}

/* ── Cross-Group Member Search & Assign ── */
export async function searchMembers(query: string, limit = 20) {
  return request<{ results: any[]; count: number }>(
    `/attendance/members/search?q=${encodeURIComponent(query)}&limit=${limit}`,
  );
}

export async function assignMemberToGroup(personId: string, groupId: string) {
  return request<{ success: boolean; message: string }>(
    `/attendance/members/assign?person_id=${encodeURIComponent(personId)}&group_id=${encodeURIComponent(groupId)}`,
    { method: "POST" },
  );
}

/* ── Export helpers (client-side) ── */
export function downloadExcel(
  records: Array<{ enrollment_no: string; status: string }>,
  filename: string,
) {
  import("xlsx").then((XLSX) => {
    const ws = XLSX.utils.json_to_sheet(
      records.map((r) => ({ EnrolmentNo: r.enrollment_no, Status: r.status })),
    );
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Attendance");
    XLSX.writeFile(wb, filename);
  });
}
