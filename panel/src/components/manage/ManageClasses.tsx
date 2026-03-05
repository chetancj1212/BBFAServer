"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  ArrowLeft,
  Search,
  Loader2,
  AlertCircle,
  BookOpen,
  Users,
  UserPlus,
  Plus,
  X,
  ChevronDown,
  ChevronUp,
  CheckSquare,
  CheckCheck,
} from "lucide-react";
import { usePanelStore } from "@/store/panelStore";
import {
  getClasses,
  getClassMembers,
  getRooms,
  updateClass,
  getSubjects,
  createSubject,
  deleteSubject,
  searchMembers,
  assignMemberToGroup,
  assignSubjectMembers,
  getSubjectMembers,
  removeSubjectMember,
} from "@/services/api";
import type { ClassInfo, Subject } from "@/types";

export interface Member {
  person_id: string;
  name: string;
  enrollment_no: string;
  group_id?: string;
  group_name?: string;
}

export default function ManageClasses() {
  const { setView, rooms, setRooms, classes, setClasses } = usePanelStore();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedClass, setExpandedClass] = useState<string | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [membersLoading, setMembersLoading] = useState(false);

  // Subject state
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [subjectsLoading, setSubjectsLoading] = useState(false);
  const [newSubject, setNewSubject] = useState("");
  const [addingSubject, setAddingSubject] = useState(false);
  const [selectedSubject, setSelectedSubject] = useState<string | null>(null);
  const [subjectMemberIds, setSubjectMemberIds] = useState<Set<string>>(
    new Set(),
  );

  // Search-assign state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Member[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchEmpty, setSearchEmpty] = useState(false);
  const [assigning, setAssigning] = useState<string | null>(null);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Device linking state
  const [linkingClass, setLinkingClass] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [classRes, roomRes] = await Promise.all([getClasses(), getRooms()]);
      
      const classList = Array.isArray(classRes) ? classRes : (classRes as { groups?: Record<string, unknown>[] }).groups || [];
      setClasses(
        classList.map((g: Record<string, unknown>) => ({
          group_id: (g.id || g.group_id) as string,
          name: g.name as string,
          total_students: (g.member_count || 0) as number,
          room_id: g.room_id as string | undefined,
          description: g.description as string | undefined,
        })),
      );
      
      const roomList = (roomRes as { rooms?: Record<string, unknown>[] }).rooms || [];
      setRooms(
        roomList.map((r: Record<string, unknown>) => ({
          id: r.id as string,
          room_no: r.room_no as string,
          device_name: r.device_name as string,
          description: r.description as string | undefined,
        })),
      );
    } catch {
      setError("Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [setClasses, setRooms]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleExpand = useCallback(
    async (groupId: string) => {
      if (expandedClass === groupId) {
        setExpandedClass(null);
        return;
      }
      setExpandedClass(groupId);
      setMembersLoading(true);
      setSubjectsLoading(true);
      setSearchQuery("");
      setSearchResults([]);
      try {
        const [memberRes, subjectRes] = await Promise.all([
          getClassMembers(groupId),
          getSubjects(groupId),
        ]);
        setMembers(Array.isArray(memberRes) ? memberRes : []);
        setSubjects(Array.isArray(subjectRes) ? subjectRes : []);
      } catch {
        setMembers([]);
        setSubjects([]);
      } finally {
        setMembersLoading(false);
        setSubjectsLoading(false);
        setSelectedSubject(null);
        setSubjectMemberIds(new Set());
      }
    },
    [expandedClass],
  );

  // Subject Member Management
  const handleSelectSubject = async (subjectId: string | null) => {
    if (selectedSubject === subjectId) {
      setSelectedSubject(null);
      setSubjectMemberIds(new Set());
      return;
    }

    setSelectedSubject(subjectId);
    if (!subjectId) return;

    try {
      const res = await getSubjectMembers(subjectId) as { results?: { person_id: string }[] };
      const ids = new Set((res.results || []).map((m) => m.person_id));
      setSubjectMemberIds(ids);
    } catch {
      setSubjectMemberIds(new Set());
    }
  };

  const handleToggleSubjectMember = async (personId: string) => {
    if (!selectedSubject) return;

    const isEnrolled = subjectMemberIds.has(personId);
    try {
      if (isEnrolled) {
        await removeSubjectMember(selectedSubject, personId);
        setSubjectMemberIds((prev) => {
          const next = new Set(prev);
          next.delete(personId);
          return next;
        });
      } else {
        await assignSubjectMembers(selectedSubject, [personId]);
        setSubjectMemberIds((prev) => {
          const next = new Set(prev);
          next.add(personId);
          return next;
        });
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update subject membership");
    }
  };

  // Select All / Deselect All for subject enrollment
  const handleSelectAllSubjectMembers = async () => {
    if (!selectedSubject || members.length === 0) return;

    const allEnrolled = members.every((m: Member) =>
      subjectMemberIds.has(m.person_id),
    );

    try {
      if (allEnrolled) {
        // Deselect all: remove each enrolled member
        for (const m of members) {
          if (subjectMemberIds.has(m.person_id)) {
            await removeSubjectMember(selectedSubject, m.person_id);
          }
        }
        setSubjectMemberIds(new Set());
      } else {
        // Select all: enroll all non-enrolled members
        const toEnroll = members
          .filter((m: Member) => !subjectMemberIds.has(m.person_id))
          .map((m: Member) => m.person_id);
        if (toEnroll.length > 0) {
          await assignSubjectMembers(selectedSubject, toEnroll);
        }
        setSubjectMemberIds(new Set(members.map((m: Member) => m.person_id)));
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update subject membership");
    }
  };

  // Search for existing students to add (debounced)
  const handleSearch = useCallback((q: string) => {
    setSearchQuery(q);
    setSearchEmpty(false);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    if (q.length < 2) {
      setSearchResults([]);
      setSearchLoading(false);
      return;
    }
    setSearchLoading(true);
    searchTimer.current = setTimeout(async () => {
      try {
        const res = await searchMembers(q);
        setSearchResults(res.results || []);
        setSearchEmpty((res.results || []).length === 0);
      } catch (err: unknown) {
        setSearchResults([]);
        setSearchEmpty(true);
        setError(err instanceof Error ? err.message : "Search failed");
      } finally {
        setSearchLoading(false);
      }
    }, 300);
  }, []);

  // Assign student to current class
  const handleAssign = async (personId: string) => {
    if (!expandedClass) return;
    setAssigning(personId);
    try {
      await assignMemberToGroup(personId, expandedClass);
      // Refresh members
      const memberRes = await getClassMembers(expandedClass);
      setMembers(Array.isArray(memberRes) ? memberRes : []);
      setSearchQuery("");
      setSearchResults([]);
      // Refresh class counts
      loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to assign student");
    } finally {
      setAssigning(null);
    }
  };

  // Add subject
  const handleAddSubject = async () => {
    if (!expandedClass || !newSubject.trim()) return;
    setAddingSubject(true);
    try {
      await createSubject(expandedClass, newSubject.trim());
      const subjectRes = await getSubjects(expandedClass);
      setSubjects(Array.isArray(subjectRes) ? subjectRes : []);
      setNewSubject("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to add subject");
    } finally {
      setAddingSubject(false);
    }
  };

  // Delete subject
  const handleDeleteSubject = async (subjectId: string) => {
    try {
      await deleteSubject(subjectId);
      setSubjects((prev) => prev.filter((s) => s.id !== subjectId));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete subject");
    }
  };

  // Link device
  const handleLinkDevice = async (groupId: string, roomId: string | null) => {
    try {
      await updateClass(groupId, { room_id: roomId });
      setLinkingClass(null);
      loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to link device");
    }
  };

  const getLinkedRoom = (cls: ClassInfo) =>
    rooms.find((r) => r.id === cls.room_id);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setView("dashboard")}
          className="p-2 rounded-lg bg-transparent border-none hover:bg-white/5 text-[var(--text-secondary)] hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <h2 className="text-lg font-semibold text-white tracking-tight">
          Manage Classes
        </h2>
      </div>

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
          <button
            onClick={() => setError("")}
            className="ml-auto text-red-400/60 hover:text-red-400 bg-transparent border-none"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-white/50" />
        </div>
      ) : classes.length === 0 ? (
        <p className="text-center py-12 text-sm text-[var(--text-tertiary)]">
          No classes configured. Add classes via the super admin panel.
        </p>
      ) : (
        <div className="space-y-3">
          {classes.map((cls) => {
            const linked = getLinkedRoom(cls);
            const isExpanded = expandedClass === cls.group_id;

            return (
              <div
                key={cls.group_id}
                className="rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-primary)] overflow-hidden"
              >
                {/* Class header */}
                <button
                  onClick={() => handleExpand(cls.group_id)}
                  className="w-full flex items-center justify-between p-4 hover:bg-white/[0.02] transition-colors bg-transparent border-none text-left"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-white/8">
                      <BookOpen className="w-4 h-4 text-white/60" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-white">
                        {cls.name}
                      </p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-xs text-[var(--text-tertiary)] flex items-center gap-1">
                          <Users className="w-3 h-3" /> {cls.total_students}{" "}
                          students
                        </span>
                        {linked && (
                          <span className="text-xs text-white/40 font-mono">
                            · {linked.device_name}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-[var(--text-tertiary)]" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-[var(--text-tertiary)]" />
                  )}
                </button>

                {/* Expanded content */}
                {isExpanded && (
                  <div className="border-t border-[var(--border-primary)] p-4 space-y-5 animate-slide-up">
                    {/* Device linking */}
                    <section>
                      <p className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider mb-2">
                        Linked Device
                      </p>
                      {linkingClass === cls.group_id ? (
                        <div className="flex flex-wrap gap-2">
                          {rooms.map((r) => (
                            <button
                              key={r.id}
                              onClick={() =>
                                handleLinkDevice(cls.group_id, r.id)
                              }
                              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                                cls.room_id === r.id
                                  ? "bg-cyan-500/10 border-cyan-500/25 text-white"
                                  : "bg-[var(--surface-primary)] border-[var(--border-primary)] text-[var(--text-secondary)] hover:border-white/20 hover:text-white"
                              }`}
                            >
                              {r.room_no} ({r.device_name})
                            </button>
                          ))}
                          <button
                            onClick={() => handleLinkDevice(cls.group_id, null)}
                            className="px-3 py-1.5 rounded-lg text-xs font-medium border bg-red-500/5 border-red-500/20 text-red-400/80 hover:bg-red-500/10 transition-all"
                          >
                            Unlink
                          </button>
                          <button
                            onClick={() => setLinkingClass(null)}
                            className="px-3 py-1.5 rounded-lg text-xs text-[var(--text-tertiary)] bg-transparent border-none hover:text-white"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setLinkingClass(cls.group_id)}
                          className="text-xs text-white/50 hover:text-white bg-transparent border-none transition-colors"
                        >
                          {linked
                            ? `${linked.room_no} (${linked.device_name}) — change`
                            : "Link a device →"}
                        </button>
                      )}
                    </section>

                    {/* Subjects */}
                    <section>
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">
                          Subjects
                        </p>
                        {selectedSubject && (
                          <button
                            onClick={() => handleSelectSubject(null)}
                            className="text-[10px] text-red-400/60 hover:text-red-400 bg-transparent border-none"
                          >
                            Clear Selection
                          </button>
                        )}
                      </div>
                      {subjectsLoading ? (
                        <Loader2 className="w-4 h-4 animate-spin text-white/50" />
                      ) : (
                        <>
                          <div className="flex flex-wrap gap-2 mb-2">
                            {subjects.length === 0 && (
                              <span className="text-xs text-[var(--text-tertiary)] italic">
                                No subjects yet. Add one below to manage
                                enrollment.
                              </span>
                            )}
                            {subjects.map((sub) => (
                              <button
                                key={sub.id}
                                className={`group flex items-center gap-1.5 px-3 py-1.5 rounded-lg border transition-all text-xs ${
                                  selectedSubject === sub.id
                                    ? "bg-emerald-500/15 border-emerald-500/30 text-white shadow-[0_0_12px_rgba(16,185,129,0.08)]"
                                    : "bg-[var(--surface-primary)] border-[var(--border-primary)] text-[var(--text-secondary)] hover:border-white/20 hover:text-white"
                                }`}
                                onClick={() => handleSelectSubject(sub.id)}
                              >
                                {sub.name}
                                <X
                                  className="w-3 h-3 text-[var(--text-tertiary)] hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity ml-1"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDeleteSubject(sub.id);
                                  }}
                                />
                              </button>
                            ))}
                          </div>
                          <div className="flex gap-2">
                            <input
                              type="text"
                              value={newSubject}
                              onChange={(e) => setNewSubject(e.target.value)}
                              onKeyDown={(e) =>
                                e.key === "Enter" && handleAddSubject()
                              }
                              placeholder="Add subject…"
                              className="flex-1 px-3 py-1.5 rounded-lg bg-[var(--surface-primary)] border border-[var(--border-primary)] text-white text-xs focus:border-white/30 transition-all"
                            />
                            <button
                              onClick={handleAddSubject}
                              disabled={!newSubject.trim() || addingSubject}
                              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-white/10 border border-white/20 text-white text-xs font-medium disabled:opacity-30 hover:bg-white/15 transition-all"
                            >
                              {addingSubject ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <Plus className="w-3 h-3" />
                              )}
                              Add
                            </button>
                          </div>
                        </>
                      )}
                    </section>

                    {/* Add Existing Student */}
                    <section>
                      <p className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider mb-2">
                        Add Existing Student
                      </p>
                      <div className="relative mb-2">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-tertiary)]" />
                        <input
                          type="text"
                          value={searchQuery}
                          onChange={(e) => handleSearch(e.target.value)}
                          placeholder="Search by name or enrollment…"
                          className="w-full pl-8 pr-4 py-2 rounded-lg bg-[var(--surface-primary)] border border-[var(--border-primary)] text-white text-xs focus:border-white/30 transition-all"
                        />
                      </div>
                      {searchLoading && (
                        <Loader2 className="w-4 h-4 animate-spin text-white/50 mb-2" />
                      )}
                      {searchResults.length > 0 ? (
                        <div className="space-y-1 max-h-48 overflow-y-auto custom-scroll">
                          {searchResults.map((r: Member) => {
                            const alreadyInClass = members.some(
                              (m: Member) => m.person_id === r.person_id,
                            );
                            return (
                              <div
                                key={r.person_id}
                                className="flex items-center justify-between p-2.5 rounded-lg bg-[var(--surface-primary)] border border-[var(--border-primary)]"
                              >
                                <div>
                                  <p className="text-xs font-medium text-white">
                                    {r.name}
                                  </p>
                                  <p className="text-[10px] text-[var(--text-tertiary)]">
                                    {r.enrollment_no} · {r.group_name}
                                  </p>
                                </div>
                                {alreadyInClass ? (
                                  <span className="text-[10px] text-emerald-400">
                                    Already here
                                  </span>
                                ) : assigning === r.person_id ? (
                                  <Loader2 className="w-3.5 h-3.5 animate-spin text-white/50" />
                                ) : (
                                  <>
                                    <button
                                      onClick={() => handleAssign(r.person_id)}
                                      className="flex items-center gap-1 px-2 py-1 rounded-md bg-white/10 border border-white/20 text-white text-[10px] font-medium hover:bg-white/15 transition-all"
                                    >
                                      <UserPlus className="w-3 h-3" />
                                      Assign
                                    </button>
                                    {selectedSubject && !alreadyInClass && (
                                      <button
                                        onClick={async (e) => {
                                          e.stopPropagation();
                                          await handleAssign(r.person_id);
                                          await handleToggleSubjectMember(
                                            r.person_id,
                                          );
                                        }}
                                        className="flex items-center gap-1 px-2 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[10px] font-medium hover:bg-emerald-500/20 transition-all"
                                      >
                                        <CheckSquare className="w-3 h-3" />
                                        Assign & Enroll
                                      </button>
                                    )}
                                  </>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      ) : searchEmpty && !searchLoading ? (
                        <p className="text-xs text-[var(--text-tertiary)] italic py-2">
                          No students found for &ldquo;{searchQuery}&rdquo;
                        </p>
                      ) : null}
                    </section>

                    {/* Members list */}
                    <section>
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">
                          Students ({members.length})
                          {selectedSubject && (
                            <span className="ml-2 lowercase text-white/60 font-normal">
                              — enrollment mode
                            </span>
                          )}
                        </p>
                        {selectedSubject && members.length > 0 && (
                          <button
                            onClick={handleSelectAllSubjectMembers}
                            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border transition-all text-[10px] font-semibold uppercase tracking-wider bg-[var(--surface-primary)] border-[var(--border-primary)] text-[var(--text-secondary)] hover:border-white/30 hover:text-white"
                          >
                            <CheckCheck className="w-3.5 h-3.5" />
                            {members.every((m: Member) =>
                              subjectMemberIds.has(m.person_id),
                            )
                              ? "Deselect All"
                              : "Select All"}
                          </button>
                        )}
                      </div>
                      {membersLoading ? (
                        <Loader2 className="w-4 h-4 animate-spin text-white/50" />
                      ) : members.length === 0 ? (
                        <p className="text-xs text-[var(--text-tertiary)] italic">
                          No students in this class
                        </p>
                      ) : (
                        <div className="space-y-1 max-h-60 overflow-y-auto custom-scroll">
                          {members.map((m: Member) => {
                            const isEnrolled = subjectMemberIds.has(
                              m.person_id,
                            );
                            return (
                              <div
                                key={m.person_id}
                                className={`flex items-center justify-between p-2.5 rounded-lg border transition-all ${
                                  selectedSubject
                                    ? "cursor-pointer hover:bg-white/5 select-none"
                                    : "bg-[var(--surface-primary)] border-[var(--border-primary)]"
                                } ${
                                  isEnrolled && selectedSubject
                                    ? "bg-emerald-500/10 border-emerald-500/20"
                                    : "bg-[var(--surface-primary)] border-[var(--border-primary)]"
                                }`}
                                onClick={() =>
                                  selectedSubject &&
                                  handleToggleSubjectMember(m.person_id)
                                }
                              >
                                <div className="flex items-center gap-2.5">
                                  <div
                                    className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-semibold transition-colors ${
                                      isEnrolled && selectedSubject
                                        ? "bg-emerald-500 text-white"
                                        : "bg-white/10 text-white/60"
                                    }`}
                                  >
                                    {(m.name || "?").charAt(0).toUpperCase()}
                                  </div>
                                  <div>
                                    <p className="text-xs font-medium text-white">
                                      {m.name}
                                    </p>
                                    <p className="text-[10px] text-[var(--text-tertiary)]">
                                      {m.enrollment_no || "—"}
                                    </p>
                                  </div>
                                </div>
                                {selectedSubject && (
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleToggleSubjectMember(m.person_id);
                                    }}
                                    className={`flex items-center justify-center gap-1.5 min-w-[90px] px-3 py-1.5 rounded-lg border transition-all text-[10px] font-semibold uppercase tracking-wider ${
                                      isEnrolled
                                        ? "bg-emerald-500 border-emerald-400 text-white shadow-lg shadow-emerald-500/20"
                                        : "bg-[var(--bg-secondary)] border-[var(--border-primary)] text-[var(--text-tertiary)] hover:border-white/30 hover:text-white"
                                    }`}
                                  >
                                    {isEnrolled ? (
                                      <>
                                        <CheckSquare className="w-3.5 h-3.5" />
                                        Enrolled
                                      </>
                                    ) : (
                                      <>
                                        <Plus className="w-3.5 h-3.5" />
                                        Enroll
                                      </>
                                    )}
                                  </button>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </section>
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
