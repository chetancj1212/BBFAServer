"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  ArrowLeft,
  Square,
  Users,
  UserCheck,
  UserX,
  Download,
  Trash2,
  Search,
  Loader2,
  CheckCircle,
  RefreshCw,
} from "lucide-react";
import { usePanelStore } from "@/store/panelStore";
import {
  getClassMembers,
  getAttendanceRecords,
  markManualAttendance,
  endSession,
  downloadExcel,
  deleteHistorySession,
  getSessionHistory,
} from "@/services/api";
import type { StudentRecord, SessionHistory } from "@/types";

interface MemberResponse {
  person_id: string;
  name: string;
  enrollment_no?: string;
}

interface AttendanceRecord {
  person_id: string;
  timestamp?: string;
}

export default function LiveSession() {
  const { activeSession, setActiveSession, setView } = usePanelStore();
  const [students, setStudents] = useState<StudentRecord[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [markingId, setMarkingId] = useState<string | null>(null);
  const [ending, setEnding] = useState(false);
  const [showEndModal, setShowEndModal] = useState(false);
  const [endResult, setEndResult] = useState<{
    records: StudentRecord[];
    sessionId: string;
  } | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load members + build student list
  const loadStudents = useCallback(async () => {
    if (!activeSession) return;
    try {
      const members = await getClassMembers(activeSession.group_id);
      const memberList: StudentRecord[] = (
        Array.isArray(members) ? members : []
      ).map((m: MemberResponse) => ({
        person_id: m.person_id,
        name: m.name,
        enrollment_no: m.enrollment_no || "",
        status: "absent" as const,
      }));

      // Get attendance records
      const records = await getAttendanceRecords(
        activeSession.group_id,
        activeSession.started_at,
      );
      const recordList: AttendanceRecord[] = Array.isArray(records) ? records : [];
      const presentIds = new Set(
        recordList.map((r) => r.person_id),
      );

      const updatedList = memberList.map((s) => ({
        ...s,
        status: presentIds.has(s.person_id)
          ? ("present" as const)
          : ("absent" as const),
        check_in_time: recordList.find(
          (r) => r.person_id === s.person_id,
        )?.timestamp,
      }));

      setStudents(updatedList);
      setActiveSession({
        ...activeSession,
        students: updatedList,
        total_students: updatedList.length,
        present_count: updatedList.filter((s) => s.status === "present").length,
      });
    } catch (err) {
      console.error("Failed to load students", err);
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSession?.group_id, activeSession?.started_at]);

  // Initial load
  useEffect(() => {
    loadStudents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll for live updates (WebSocket not implemented on server)
  useEffect(() => {
    if (!activeSession) return;

    pollRef.current = setInterval(loadStudents, 5000);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSession?.session_id]);

  // Manual mark
  const handleManualMark = async (personId: string) => {
    setMarkingId(personId);
    try {
      await markManualAttendance(personId);
      setStudents((prev) =>
        prev.map((s) =>
          s.person_id === personId
            ? {
                ...s,
                status: "present",
                check_in_time: new Date().toISOString(),
              }
            : s,
        ),
      );
    } catch (err) {
      console.error("Manual mark failed", err);
    } finally {
      setMarkingId(null);
    }
  };

  // End class
  const handleEndClass = async () => {
    if (!activeSession) return;
    setEnding(true);
    try {
      await endSession(activeSession.session_id);
      // Save final records for download
      setEndResult({
        records: students,
        sessionId: activeSession.session_id,
      });
      setShowEndModal(false);
    } catch (err) {
      console.error("End session failed", err);
    } finally {
      setEnding(false);
    }
  };

  // Download excel
  const handleDownload = () => {
    if (!endResult) return;
    const data = endResult.records.map((s) => ({
      enrollment_no: s.enrollment_no,
      status: s.status,
    }));
    const groupName = activeSession?.group_name || "class";
    const subjectName = activeSession?.subject_name || "general";
    const date = new Date().toISOString().slice(0, 10);
    downloadExcel(data, `${groupName}-${subjectName}-${date}.xlsx`);
  };

  // Delete records from history
  const handleDeleteRecords = async () => {
    if (!endResult) return;
    try {
      // Find the session in history and delete
      const histRes = await getSessionHistory(activeSession?.group_id, 5);
      const latestSession = (histRes.sessions || []).find(
        (s: SessionHistory) => s.id === endResult.sessionId,
      );
      if (latestSession) {
        await deleteHistorySession(latestSession.id);
      }
    } catch (err) {
      console.error("Delete failed", err);
    }
    // Go back to dashboard
    setActiveSession(null);
    setView("dashboard");
  };

  // Go back after end
  const handleGoBack = () => {
    setActiveSession(null);
    setView("dashboard");
  };

  // ----- End result screen -----
  if (endResult) {
    const presentCount = endResult.records.filter(
      (s) => s.status === "present",
    ).length;
    const totalCount = endResult.records.length;
    const rate =
      totalCount > 0 ? Math.round((presentCount / totalCount) * 100) : 0;

    return (
      <div className="space-y-6 animate-fade-in max-w-lg mx-auto">
        <div className="text-center pt-8">
          <div className="inline-flex p-3 rounded-full bg-white/10 mb-4">
            <CheckCircle className="w-10 h-10 text-white/70" />
          </div>
          <h2 className="text-xl font-semibold text-white mb-1">Class Ended</h2>
          <p className="text-sm text-[var(--text-secondary)]">
            {activeSession?.group_name} · {rate}% attendance ({presentCount}/
            {totalCount})
          </p>
        </div>

        <div className="flex flex-col gap-3">
          <button
            onClick={handleDownload}
            className="flex items-center justify-center gap-2 w-full py-3 rounded-xl bg-white/10 border border-white/20 text-white hover:bg-white/15 hover:border-white/30 transition-all font-medium text-sm"
          >
            <Download className="w-4 h-4" />
            Download Excel (EnrolmentNo. & Status)
          </button>

          <button
            onClick={handleDeleteRecords}
            className="flex items-center justify-center gap-2 w-full py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 hover:border-red-500/50 transition-all font-medium text-sm"
          >
            <Trash2 className="w-4 h-4" />
            Delete Records
          </button>

          <button
            onClick={handleGoBack}
            className="w-full py-3 rounded-xl bg-[var(--surface-primary)] border border-[var(--border-primary)] text-[var(--text-secondary)] hover:text-white hover:border-[var(--border-hover)] transition-all font-medium text-sm"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  if (!activeSession) {
    return (
      <div className="text-center py-12 text-[var(--text-secondary)]">
        <p>No active session. Start a class first.</p>
        <button
          onClick={() => setView("start-class")}
          className="mt-4 text-white/60 text-sm hover:underline bg-transparent border-none"
        >
          Go to Start Class
        </button>
      </div>
    );
  }

  // Filtered students
  const filtered = students.filter(
    (s) =>
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.enrollment_no.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const presentCount = students.filter((s) => s.status === "present").length;
  const absentCount = students.length - presentCount;

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowEndModal(true)}
            className="p-2 rounded-lg bg-transparent border-none hover:bg-white/5 text-[var(--text-secondary)] hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h2 className="text-lg font-semibold text-white tracking-tight flex items-center gap-2">
              {activeSession.group_name}
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/10 border border-white/20 text-white/70 text-xs font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-white/60 animate-pulse-dot" />
                Live
              </span>
            </h2>
            <p className="text-xs text-[var(--text-secondary)]">
              Room {activeSession.room_no} · Device {activeSession.device_name}{" "}
              {activeSession.subject_name && (
                <>· Subject <span className="text-white">{activeSession.subject_name}</span>{" "}</>
              )}
              · Started{" "}
              {new Date(activeSession.started_at).toLocaleTimeString(
                undefined,
                { hour: "numeric", minute: "2-digit" },
              )}
            </p>
          </div>
        </div>

        <button
          onClick={() => setShowEndModal(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 hover:border-red-500/50 transition-all text-sm font-medium"
        >
          <Square className="w-3.5 h-3.5" />
          End Class
        </button>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-3 gap-3">
        <div className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-primary)] text-center">
          <div className="flex items-center justify-center gap-1.5 text-[var(--text-secondary)] mb-1">
            <Users className="w-3.5 h-3.5" />
            <span className="text-xs font-medium uppercase">Total</span>
          </div>
          <p className="text-xl font-bold text-white">{students.length}</p>
        </div>
        <div className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-primary)] text-center">
          <div className="flex items-center justify-center gap-1.5 text-green-400 mb-1">
            <UserCheck className="w-3.5 h-3.5" />
            <span className="text-xs font-medium uppercase">Present</span>
          </div>
          <p className="text-xl font-bold text-green-400">{presentCount}</p>
        </div>
        <div className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-primary)] text-center">
          <div className="flex items-center justify-center gap-1.5 text-red-400 mb-1">
            <UserX className="w-3.5 h-3.5" />
            <span className="text-xs font-medium uppercase">Absent</span>
          </div>
          <p className="text-xl font-bold text-red-400">{absentCount}</p>
        </div>
      </div>

      {/* Live Activity Log */}
      {(() => {
        const recentLogs = students
          .filter((s) => s.status === "present" && s.check_in_time)
          .sort((a, b) => new Date(b.check_in_time!).getTime() - new Date(a.check_in_time!).getTime())
          .slice(0, 50);

        if (recentLogs.length === 0) return null;

        return (
          <div className="rounded-md bg-[#0A0A0A] border border-white/10 flex flex-col h-56 shadow-inner overflow-hidden animate-fade-in font-mono">
            <div className="px-3 py-2 border-b border-white/10 flex items-center justify-between bg-black/50">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-green-500 animate-pulse"></span>
                <span className="text-xs font-semibold text-green-500 uppercase tracking-widest">Live Atendee</span>
              </div>
              <span className="text-[10px] text-[var(--text-tertiary)] opacity-70">
                [ {recentLogs.length} present ]
              </span>
            </div>
            <div className="flex-1 overflow-y-auto custom-scroll p-3 space-y-2">
              {recentLogs.map((s) => (
                <div key={s.person_id} className="flex justify-between text-xs leading-relaxed hover:bg-white/5 transition-colors rounded px-1 -mx-1 text-gray-300">
                  <div className="flex gap-2 min-w-0">
                    <span className="text-white truncate">{s.name}</span>
                    <span className="text-gray-500">-</span>
                    <span className="text-gray-400">{s.enrollment_no}</span>
                  </div>
                  <span className="text-green-500/80 whitespace-nowrap ml-4">
                    {new Date(s.check_in_time!).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })}
                  </span>
                </div>
              ))}
              <div className="flex items-center gap-2 mt-2 opacity-50">
                <span className="w-2 h-4 bg-green-500 animate-pulse"></span>
                <span className="text-[10px] text-green-500">Listening for attendence . . .</span>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Search + Refresh */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-tertiary)]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by name or enrollment…"
            className="w-full pl-9 pr-4 py-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-primary)] text-white text-sm focus:border-white/30 transition-all"
          />
        </div>
        <button
          onClick={loadStudents}
          className="p-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-primary)] text-[var(--text-secondary)] hover:text-white hover:border-[var(--border-hover)] transition-all"
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Student list */}
      {loading ? (
        <div className="flex justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-white/50" />
        </div>
      ) : (
        <div className="space-y-1.5 max-h-[calc(100vh-340px)] overflow-y-auto custom-scroll">
          {filtered.length === 0 ? (
            <p className="text-center py-8 text-sm text-[var(--text-tertiary)]">
              No students found
            </p>
          ) : (
            filtered.map((student) => (
              <div
                key={student.person_id}
                className="flex items-center justify-between p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-primary)] hover:border-[var(--border-hover)] transition-all"
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold ${
                      student.status === "present"
                        ? "bg-green-500/20 text-green-400"
                        : "bg-[var(--surface-secondary)] text-[var(--text-tertiary)]"
                    }`}
                  >
                    {student.name.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-white">
                      {student.name}
                    </p>
                    <p className="text-xs text-[var(--text-tertiary)]">
                      {student.enrollment_no}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {student.status === "present" ? (
                    <span className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-green-500/10 border border-green-500/30 text-green-400 text-xs font-medium">
                      <CheckCircle className="w-3 h-3" />
                      Present
                    </span>
                  ) : markingId === student.person_id ? (
                    <Loader2 className="w-4 h-4 animate-spin text-white/50" />
                  ) : (
                    <button
                      onClick={() => handleManualMark(student.person_id)}
                      className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-[var(--surface-primary)] border border-[var(--border-primary)] text-[var(--text-secondary)] hover:bg-white/10 hover:border-white/20 hover:text-white transition-all text-xs font-medium"
                    >
                      Mark Present
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* End Class Confirmation Modal */}
      {showEndModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
          <div className="w-full max-w-sm p-6 rounded-2xl bg-[var(--surface-primary)] border border-[var(--border-primary)] shadow-2xl animate-slide-up">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-full bg-red-500/10">
                <Square className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-white">
                  End Class?
                </h3>
                <p className="text-xs text-[var(--text-secondary)]">
                  This will archive attendance and end the session.
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setShowEndModal(false)}
                className="flex-1 py-2 rounded-lg bg-[var(--surface-secondary)] border border-[var(--border-primary)] text-[var(--text-secondary)] hover:text-white transition-all text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleEndClass}
                disabled={ending}
                className="flex-1 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 hover:border-red-500/50 transition-all text-sm font-medium flex items-center justify-center gap-2"
              >
                {ending ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {ending ? "Ending…" : "End Class"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
