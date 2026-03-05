"use client";

import { useEffect, useState } from "react";
import {
  ArrowLeft,
  Clock,
  Download,
  Trash2,
  Loader2,
  Search,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { usePanelStore } from "@/store/panelStore";
import {
  getSessionHistory,
  getHistoryDetail,
  deleteHistorySession,
  downloadExcel,
} from "@/services/api";

interface HistorySession {
  id: string;
  group_id: string;
  group_name: string;
  session_name: string;
  subject_name?: string;
  started_at: string | null;
  ended_at: string | null;
  present_count: number;
  total_members: number;
  absent_count: number;
  late_count: number;
}

interface DetailRecord {
  person_name?: string;
  name?: string;
  enrollment_no?: string;
  person_id?: string;
  status?: string;
}

export default function History() {
  const { setView } = usePanelStore();
  const [sessions, setSessions] = useState<HistorySession[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detailRecords, setDetailRecords] = useState<DetailRecord[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    setLoading(true);
    try {
      const res = await getSessionHistory(undefined, 100);
      setSessions(res.sessions || []);
    } catch (err) {
      console.error("Failed to load history", err);
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = async (sessionId: string) => {
    if (expandedId === sessionId) {
      setExpandedId(null);
      setDetailRecords([]);
      return;
    }
    setExpandedId(sessionId);
    setDetailLoading(true);
    try {
      const res = await getHistoryDetail(sessionId);
      setDetailRecords(res.records || []);
    } catch {
      setDetailRecords([]);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleDelete = async (sessionId: string) => {
    if (!confirm("Delete this session record?")) return;
    setDeleting(sessionId);
    try {
      await deleteHistorySession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (expandedId === sessionId) {
        setExpandedId(null);
        setDetailRecords([]);
      }
    } catch (err) {
      console.error("Delete failed", err);
    } finally {
      setDeleting(null);
    }
  };

  const handleExport = (sessionId: string) => {
    const session = sessions.find((s) => s.id === sessionId);
    if (!session) return;

    // Need detail records for export
    getHistoryDetail(sessionId).then((res) => {
      const records = (res.records || []).map((r: DetailRecord) => ({
        enrollment_no: r.enrollment_no || r.person_id || "",
        status: r.status || "absent",
      }));
      const date = session.ended_at
        ? new Date(session.ended_at).toISOString().slice(0, 10)
        : new Date().toISOString().slice(0, 10);
      const groupName = session.group_name || "class";
      const subjectName = session.subject_name || "general";
      downloadExcel(records, `${groupName}-${subjectName}-${date}.xlsx`);
    });
  };

  const filtered = sessions.filter(
    (s) =>
      (s.group_name || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (s.session_name || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (s.subject_name || "").toLowerCase().includes(searchQuery.toLowerCase()),
  );

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setView("dashboard")}
          className="p-2 rounded-lg bg-transparent border-none hover:bg-white/5 text-[var(--text-secondary)] hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <h2 className="text-lg font-semibold text-white tracking-tight">
          Session History
        </h2>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-tertiary)]" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search by class name…"
          className="w-full pl-9 pr-4 py-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-primary)] text-white text-sm focus:border-white/30 transition-all"
        />
      </div>

      {/* List */}
      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-white/50" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <div className="p-3 rounded-full bg-[var(--surface-secondary)] text-[var(--text-secondary)] mb-3">
            <Clock className="w-6 h-6" />
          </div>
          <p className="text-sm text-[var(--text-secondary)]">
            No history found
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((session) => {
            const isExpanded = expandedId === session.id;
            const d = new Date(session.ended_at || session.started_at || "");
            const rate =
              session.total_members > 0
                ? Math.round(
                    (session.present_count / session.total_members) * 100,
                  )
                : 0;

            return (
              <div
                key={session.id}
                className="rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-primary)] overflow-hidden transition-all"
              >
                {/* Row */}
                <div
                  className="flex items-center justify-between p-4 cursor-pointer hover:bg-[var(--surface-secondary)] transition-colors"
                  onClick={() => toggleExpand(session.id)}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="flex-shrink-0">
                      {isExpanded ? (
                        <ChevronUp className="w-4 h-4 text-[var(--text-tertiary)]" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-[var(--text-tertiary)]" />
                      )}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-white truncate">
                        {session.group_name || session.session_name}
                      </p>
                      <p className="text-xs text-[var(--text-secondary)]">
                        {session.subject_name && (
                          <span className="text-white/50">{session.subject_name} · </span>
                        )}
                        {d.toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })}{" "}
                        ·{" "}
                        {d.toLocaleTimeString(undefined, {
                          hour: "numeric",
                          minute: "2-digit",
                        })}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <p className="text-sm font-medium text-white">{rate}%</p>
                      <p className="text-xs text-[var(--text-secondary)]">
                        {session.present_count}/{session.total_members}
                      </p>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleExport(session.id);
                        }}
                        className="p-1.5 rounded-md hover:bg-white/5 text-[var(--text-secondary)] hover:text-white transition-colors border-none bg-transparent"
                        title="Download Excel"
                      >
                        <Download className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(session.id);
                        }}
                        disabled={deleting === session.id}
                        className="p-1.5 rounded-md hover:bg-red-500/10 text-[var(--text-secondary)] hover:text-red-400 transition-colors border-none bg-transparent"
                        title="Delete"
                      >
                        {deleting === session.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Expanded detail */}
                {isExpanded && (
                  <div className="border-t border-[var(--border-primary)] p-4">
                    {detailLoading ? (
                      <div className="flex justify-center py-4">
                        <Loader2 className="w-5 h-5 animate-spin text-white/50" />
                      </div>
                    ) : detailRecords.length === 0 ? (
                      <p className="text-sm text-[var(--text-tertiary)] text-center py-4">
                        No records found
                      </p>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                          <thead>
                            <tr className="text-xs uppercase text-[var(--text-secondary)] font-medium">
                              <th className="pb-2 pr-4">Name</th>
                              <th className="pb-2 pr-4">EnrolmentNo.</th>
                              <th className="pb-2 text-center">Status</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-[var(--border-primary)]">
                            {detailRecords.map((r: DetailRecord, i: number) => (
                              <tr
                                key={i}
                                className="hover:bg-white/3 transition-colors"
                              >
                                <td className="py-2 pr-4 text-white">
                                  {r.person_name || r.name || "—"}
                                </td>
                                <td className="py-2 pr-4 text-[var(--text-secondary)] font-mono text-xs">
                                  {r.enrollment_no || "—"}
                                </td>
                                <td className="py-2 text-center">
                                  <span
                                    className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                                      r.status === "present"
                                        ? "bg-green-500/10 text-green-400"
                                        : "bg-red-500/10 text-red-400"
                                    }`}
                                  >
                                    {r.status === "present"
                                      ? "Present"
                                      : "Absent"}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
