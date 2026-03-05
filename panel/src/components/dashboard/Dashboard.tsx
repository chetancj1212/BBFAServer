"use client";

import { useEffect, useState, useCallback } from "react";
import { Play, Users, ClipboardList, Clock } from "lucide-react";
import { usePanelStore } from "@/store/panelStore";
import {
  getClasses,
  getActiveSessions,
  getSessionHistory,
} from "@/services/api";

interface DashboardSession {
  id: string;
  group_id: string;
  name?: string;
  status: string;
  started_at: string;
  total_members: number;
  present_count: number;
}

interface DashboardHistory {
  id: string;
  group_name?: string;
  session_name?: string;
  ended_at?: string;
  started_at?: string;
  archived_at?: string;
  total_members: number;
  present_count: number;
}

interface GroupResponse {
  id?: string;
  group_id?: string;
  name: string;
  member_count?: number;
}

interface ClassResponse {
  groups?: GroupResponse[];
}

export default function Dashboard() {
  const { setView, classes, setClasses } = usePanelStore();
  const [activeSessions, setActiveSessions] = useState<DashboardSession[]>([]);
  const [recentHistory, setRecentHistory] = useState<DashboardHistory[]>([]);
  const [loading, setLoading] = useState(true);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    try {
      // Load classes
      const classRes = await getClasses();
      const groups = Array.isArray(classRes)
        ? classRes
        : (classRes as ClassResponse).groups || [];
      setClasses(
        groups.map((g: GroupResponse) => ({
          group_id: g.id || g.group_id || "",
          name: g.name,
          total_students: g.member_count || 0,
        })),
      );

      // Load active sessions
      const sessRes = await getActiveSessions();
      setActiveSessions(
        (sessRes.sessions || []).filter(
          (s: DashboardSession) => s.status === "active" || s.status === "waiting",
        ),
      );

      // Load recent history
      const histRes = await getSessionHistory(undefined, 5);
      setRecentHistory(histRes.sessions || []);
    } catch {
      // Backend offline handled in header
    } finally {
      setLoading(false);
    }
  }, [setClasses]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const totalStudents = classes.reduce((sum, c) => sum + c.total_students, 0);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Status bar */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white tracking-tight">
          Dashboard
        </h2>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard
          icon={<ClipboardList className="w-5 h-5" />}
          label="Classes"
          value={classes.length}
        />
        <StatCard
          icon={<Users className="w-5 h-5" />}
          label="Total Students"
          value={totalStudents}
        />
        <StatCard
          icon={<Play className="w-5 h-5" />}
          label="Active Sessions"
          value={activeSessions.length}
          accent={activeSessions.length > 0}
        />
        <StatCard
          icon={<Clock className="w-5 h-5" />}
          label="History Records"
          value={recentHistory.length}
        />
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <ActionCard
          icon={<Play className="w-6 h-6 text-white/60" />}
          title="Start a Class"
          description="Begin an attendance session"
          onClick={() => setView("start-class")}
        />
        <ActionCard
          icon={<Clock className="w-6 h-6 text-[var(--text-secondary)]" />}
          title="View History"
          description="Browse past sessions & export"
          onClick={() => setView("history")}
        />
        <ActionCard
          icon={<ClipboardList className="w-6 h-6 text-white/60" />}
          title="Manage Rooms"
          description="Add rooms & device mappings"
          onClick={() => setView("manage-rooms")}
        />
        <ActionCard
          icon={<Users className="w-6 h-6 text-white/60" />}
          title="Manage Classes"
          description="Link devices & manage students"
          onClick={() => setView("manage-classes")}
        />
      </div>

      {/* Active sessions */}
      {activeSessions.length > 0 && (
        <section>
          <h3 className="text-sm font-medium text-[var(--text-secondary)] uppercase tracking-wider mb-3">
            Active Sessions
          </h3>
          <div className="space-y-2">
            {activeSessions.map((s) => (
              <div
                key={s.id}
                className="flex items-center justify-between p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-primary)] hover:border-[var(--border-hover)] transition-all cursor-pointer"
                onClick={() => {
                  usePanelStore.getState().setActiveSession({
                    session_id: s.id,
                    group_id: s.group_id,
                    group_name: s.name || "Class",
                    room_no: "",
                    device_name: "",
                    started_at: s.started_at,
                    students: [],
                    total_students: s.total_members || 0,
                    present_count: s.present_count || 0,
                  });
                  setView("live-session");
                }}
              >
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse-dot" />
                  <div>
                    <p className="text-sm font-medium text-white">
                      {s.name || "Class Session"}
                    </p>
                    <p className="text-xs text-[var(--text-secondary)]">
                      {s.present_count || 0}/{s.total_members || 0} present
                    </p>
                  </div>
                </div>
                <span className="text-xs text-white/60 font-medium">
                  View →
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Recent history */}
      {recentHistory.length > 0 && (
        <section>
          <h3 className="text-sm font-medium text-[var(--text-secondary)] uppercase tracking-wider mb-3">
            Recent History
          </h3>
          <div className="overflow-x-auto rounded-xl border border-[var(--border-primary)] bg-[var(--bg-secondary)]">
            <table className="w-full text-left text-sm">
              <thead className="bg-[var(--surface-primary)] text-xs uppercase text-[var(--text-secondary)] font-medium">
                <tr>
                  <th className="px-4 py-2.5">Class</th>
                  <th className="px-4 py-2.5">Date</th>
                  <th className="px-4 py-2.5 text-center">Attendance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-primary)]">
                {recentHistory.map((h) => {
                  const d = new Date(
                    h.ended_at || h.started_at || h.archived_at || "",
                  );
                  const rate =
                    h.total_members > 0
                      ? Math.round((h.present_count / h.total_members) * 100)
                      : 0;
                  return (
                    <tr
                      key={h.id}
                      className="hover:bg-[var(--surface-secondary)] transition-colors"
                    >
                      <td className="px-4 py-2.5 text-white font-medium">
                        {h.group_name || h.session_name}
                      </td>
                      <td className="px-4 py-2.5 text-[var(--text-secondary)]">
                        {d.toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                        })}
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        <span className="text-white font-medium">{rate}%</span>
                        <span className="text-[var(--text-secondary)] text-xs ml-1">
                          ({h.present_count}/{h.total_members})
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {loading && (
        <div className="flex justify-center py-8">
          <div className="w-8 h-8 border-2 border-white/10 border-t-white/60 rounded-full animate-spin" />
        </div>
      )}
    </div>
  );
}

/* ── Sub-components ── */

function StatCard({
  icon,
  label,
  value,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  accent?: boolean;
}) {
  return (
    <div className="p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-primary)]">
      <div
        className={`mb-2 ${accent ? "text-white" : "text-[var(--text-secondary)]"}`}
      >
        {icon}
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
      <p className="text-xs text-[var(--text-secondary)] font-medium uppercase tracking-wider">
        {label}
      </p>
    </div>
  );
}

function ActionCard({
  icon,
  title,
  description,
  onClick,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex items-start gap-4 p-5 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-primary)] hover:border-[var(--border-hover)] hover:bg-[var(--surface-secondary)] transition-all text-left w-full"
    >
      <div className="mt-0.5">{icon}</div>
      <div>
        <h3 className="text-sm font-semibold text-white mb-0.5">{title}</h3>
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
          {description}
        </p>
      </div>
    </button>
  );
}
