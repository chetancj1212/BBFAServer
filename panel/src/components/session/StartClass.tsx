"use client";

import { useEffect, useState } from "react";
import {
  ArrowLeft,
  Play,
  MapPin,
  BookOpen,
  Loader2,
  AlertCircle,
  Users,
  Tag,
} from "lucide-react";
import { usePanelStore } from "@/store/panelStore";
import {
  getRooms,
  getClasses,
  getClassMembers,
  getSubjects,
  getSubjectMembers,
  createAndStartSession,
} from "@/services/api";
import type { Room, ClassInfo, Subject } from "@/types";

export default function StartClass() {
  const { setView, rooms, setRooms, classes, setClasses, setActiveSession } =
    usePanelStore();

  const [selectedRoom, setSelectedRoom] = useState<Room | null>(null);
  const [selectedClass, setSelectedClass] = useState<ClassInfo | null>(null);
  const [selectedSubject, setSelectedSubject] = useState<Subject | null>(null);
  const [classSubjects, setClassSubjects] = useState<Subject[]>([]);
  const [memberCount, setMemberCount] = useState<number>(0);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [roomRes, classRes] = await Promise.all([getRooms(), getClasses()]);
      setRooms(
        (roomRes.rooms || []).map((r: any) => ({
          id: r.id,
          room_no: r.room_no,
          device_name: r.device_name,
          description: r.description,
        })),
      );
      setClasses(
        (Array.isArray(classRes)
          ? classRes
          : (classRes as any).groups || []
        ).map((g: any) => ({
          group_id: g.id || g.group_id,
          name: g.name,
          total_students: g.member_count || 0,
        })),
      );
    } catch {
      setError("Failed to load rooms/classes");
    } finally {
      setLoading(false);
    }
  };

  // Load students/subjects when class is selected
  useEffect(() => {
    if (!selectedClass) {
      setClassSubjects([]);
      setSelectedSubject(null);
      setMemberCount(0);
      return;
    }

    // Reset subject when class changes
    setSelectedSubject(null);
    setMemberCount(selectedClass.total_students);

    // Refresh class member count
    getClassMembers(selectedClass.group_id)
      .then((members) => {
        const count = Array.isArray(members) ? members.length : 0;
        setMemberCount(count);
      })
      .catch(() => {});

    // Load subjects for this class
    getSubjects(selectedClass.group_id)
      .then((subs) => setClassSubjects(Array.isArray(subs) ? subs : []))
      .catch(() => setClassSubjects([]));
  }, [selectedClass?.group_id]);

  // Load subject-specific member count when subject is selected
  useEffect(() => {
    if (!selectedSubject) {
      if (selectedClass) {
        getClassMembers(selectedClass.group_id)
          .then((members) => {
            const count = Array.isArray(members) ? members.length : 0;
            setMemberCount(count);
          })
          .catch(() => setMemberCount(selectedClass.total_students));
      }
      return;
    }

    getSubjectMembers(selectedSubject.id)
      .then((res) => {
        setMemberCount(res.count);
      })
      .catch(() => {
        // Fallback or keep current if error
      });
  }, [selectedSubject?.id]);

  const handleStart = async () => {
    if (!selectedRoom || !selectedClass || !selectedSubject) return;
    setStarting(true);
    setError("");

    try {
      const res = await createAndStartSession(selectedClass.group_id, selectedSubject.id);
      setActiveSession({
        session_id: res.session_id,
        group_id: selectedClass.group_id,
        group_name: selectedClass.name,
        room_no: selectedRoom.room_no,
        device_name: selectedRoom.device_name,
        started_at: res.started_at,
        subject_name: res.subject_name || selectedSubject.name,
        students: [],
        total_students: memberCount,
        present_count: 0,
      });
      setView("live-session");
    } catch (err: any) {
      setError(err.message || "Failed to start session");
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Back + Title */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setView("dashboard")}
          className="p-2 rounded-lg bg-transparent border-none hover:bg-white/5 text-[var(--text-secondary)] hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <h2 className="text-lg font-semibold text-white tracking-tight">
          Start a Class
        </h2>
      </div>

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-white/50" />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Step 1: Class selection */}
          <section className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-[var(--text-secondary)]">
              <BookOpen className="w-4 h-4" />
              <span className="uppercase tracking-wider">
                Step 1 — Select Class
              </span>
            </div>
            <div className="space-y-2">
              {classes.length === 0 ? (
                <p className="text-sm text-[var(--text-tertiary)] italic p-4 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-primary)]">
                  No classes configured yet.
                </p>
              ) : (
                classes.map((cls) => (
                  <button
                    key={cls.group_id}
                    onClick={() => {
                      setSelectedClass(cls);
                      setSelectedSubject(null);
                    }}
                    className={`w-full flex items-center justify-between p-4 rounded-xl border transition-all text-left ${
                      selectedClass?.group_id === cls.group_id
                        ? "bg-cyan-500/10 border-cyan-500/25 text-white"
                        : "bg-[var(--bg-secondary)] border-[var(--border-primary)] text-[var(--text-secondary)] hover:border-[var(--border-hover)] hover:text-white"
                    }`}
                  >
                    <div>
                      <p className="text-sm font-medium">{cls.name}</p>
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-[var(--text-tertiary)]">
                      <Users className="w-3.5 h-3.5" />
                      <span>{cls.total_students}</span>
                    </div>
                  </button>
                ))
              )}
            </div>
          </section>

          {/* Step 2: Subject selection (Required) */}
          <section className={`space-y-3 transition-opacity ${!selectedClass ? "opacity-30 pointer-events-none" : ""}`}>
            <div className="flex items-center gap-2 text-sm font-medium text-[var(--text-secondary)]">
              <Tag className="w-4 h-4" />
              <span className="uppercase tracking-wider">
                Step 2 — Select Subject
              </span>
            </div>
            <div className="space-y-2">
              {!selectedClass ? (
                <p className="text-xs text-[var(--text-tertiary)] italic">Select a class first</p>
              ) : classSubjects.length === 0 ? (
                <p className="text-sm text-[var(--text-tertiary)] italic p-4 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-primary)]">
                  No subjects found for this class. Add subjects in Class Management.
                </p>
              ) : (
                classSubjects.map((sub) => (
                  <button
                    key={sub.id}
                    onClick={() => setSelectedSubject(sub)}
                    className={`w-full flex items-center justify-between p-4 rounded-xl border transition-all text-left ${
                      selectedSubject?.id === sub.id
                        ? "bg-cyan-500/10 border-cyan-500/25 text-white"
                        : "bg-[var(--bg-secondary)] border-[var(--border-primary)] text-[var(--text-secondary)] hover:border-[var(--border-hover)] hover:text-white"
                    }`}
                  >
                    <p className="text-sm font-medium">{sub.name}</p>
                    <div className="flex items-center gap-1.5 text-xs text-[var(--text-tertiary)]">
                      <Tag className="w-3 h-3" />
                    </div>
                  </button>
                ))
              )}
            </div>
          </section>

          {/* Step 3: Room selection */}
          <section className={`space-y-3 lg:col-span-2 transition-opacity ${!selectedSubject ? "opacity-30 pointer-events-none" : ""}`}>
            <div className="flex items-center gap-2 text-sm font-medium text-[var(--text-secondary)]">
              <MapPin className="w-4 h-4" />
              <span className="uppercase tracking-wider">
                Step 3 — Select Room
              </span>
            </div>
            {rooms.length === 0 ? (
              <p className="text-sm text-[var(--text-tertiary)] italic p-4 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-primary)]">
                No rooms configured. Add rooms via the backend.
              </p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {rooms.map((room) => (
                  <button
                    key={room.id}
                    onClick={() => setSelectedRoom(room)}
                    className={`flex items-center justify-between p-4 rounded-xl border transition-all text-left ${
                      selectedRoom?.id === room.id
                        ? "bg-cyan-500/10 border-cyan-500/25 text-white"
                        : "bg-[var(--bg-secondary)] border-[var(--border-primary)] text-[var(--text-secondary)] hover:border-[var(--border-hover)] hover:text-white"
                    }`}
                  >
                    <div>
                      <p className="text-sm font-medium">{room.room_no}</p>
                      <p className="text-xs text-[var(--text-tertiary)] mt-0.5 font-mono">
                        {room.device_name}
                      </p>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      {/* Summary + Start */}
      {selectedRoom && selectedClass && selectedSubject && (
        <div className="p-5 rounded-xl bg-[var(--surface-primary)] border border-[var(--border-primary)] animate-slide-up">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <p className="text-sm text-white font-medium">Ready to start session</p>
              <p className="text-xs text-[var(--text-secondary)]">
                Class: <span className="text-white">{selectedClass.name}</span>{" "}
                · Subject: <span className="text-white">{selectedSubject.name}</span>{" "}
                · Room: <span className="text-white">{selectedRoom.room_no}</span>{" "}
                · <span className="text-white">{memberCount}</span> students
              </p>
              {selectedSubject && memberCount === 0 && (
                <p className="text-[10px] text-amber-500 mt-1 flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" />
                  No students are enrolled in this subject. Check &quot;Class Management&quot; to assign them.
                </p>
              )}
            </div>
            <button
              onClick={handleStart}
              disabled={starting}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-lg font-medium text-sm transition-all ${
                starting
                  ? "bg-white/5 text-white/30 border-white/10 cursor-not-allowed"
                  : "bg-white/10 text-white border border-white/20 hover:bg-white/15 hover:border-white/30"
              }`}
            >
              {starting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              {starting ? "Starting…" : "Start Class"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

