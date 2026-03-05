"use client";

import { useEffect, useState } from "react";
import {
  Plus,
  Trash2,
  MapPin,
  Cpu,
  Loader2,
  AlertCircle,
  ArrowLeft,
  FileText,
} from "lucide-react";
import { usePanelStore } from "@/store/panelStore";
import { getRooms, createRoom, deleteRoom } from "@/services/api";
import type { Room } from "@/types";

export default function ManageRooms() {
  const { setView, rooms, setRooms } = usePanelStore();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);

  /* form fields */
  const [roomNo, setRoomNo] = useState("");
  const [deviceName, setDeviceName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    loadRooms();
  }, []);

  const loadRooms = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await getRooms();
      setRooms(
        (res.rooms || []).map((r: any) => ({
          id: r.id,
          room_no: r.room_no,
          device_name: r.device_name,
          description: r.description,
        })),
      );
    } catch {
      setError("Failed to load rooms");
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!roomNo.trim() || !deviceName.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      await createRoom(roomNo.trim(), deviceName.trim(), description.trim());
      setRoomNo("");
      setDeviceName("");
      setDescription("");
      setShowForm(false);
      await loadRooms();
    } catch (err: any) {
      setError(err.message || "Failed to create room");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (room: Room) => {
    if (!confirm(`Delete room ${room.room_no}?`)) return;
    try {
      await deleteRoom(room.id);
      await loadRooms();
    } catch (err: any) {
      setError(err.message || "Failed to delete room");
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setView("dashboard")}
            className="p-1.5 rounded-md hover:bg-white/5 text-[var(--text-secondary)] hover:text-white transition-colors border-none bg-transparent"
          >
            <ArrowLeft size={18} />
          </button>
          <div>
            <h1 className="text-lg font-semibold text-white">Manage Rooms</h1>
            <p className="text-xs text-[var(--text-tertiary)]">
              Configure room → ESP device associations
            </p>
          </div>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="btn-primary flex items-center gap-2 text-sm"
        >
          <Plus size={16} />
          Add Room
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 rounded-lg px-4 py-3">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {/* Create Form */}
      {showForm && (
        <form
          onSubmit={handleCreate}
          className="bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-xl p-5 space-y-4 animate-slide-up"
        >
          <h3 className="text-sm font-medium text-white">New Room</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-[var(--text-secondary)] mb-1.5">
                Room Number *
              </label>
              <input
                type="text"
                value={roomNo}
                onChange={(e) => setRoomNo(e.target.value)}
                placeholder="e.g. B_106"
                required
                className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-white text-sm placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-white/30"
              />
            </div>
            <div>
              <label className="block text-xs text-[var(--text-secondary)] mb-1.5">
                ESP Device Name *
              </label>
              <input
                type="text"
                value={deviceName}
                onChange={(e) => setDeviceName(e.target.value)}
                placeholder="e.g. S3B_106"
                required
                className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-white text-sm placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-white/30"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs text-[var(--text-secondary)] mb-1.5">
              Description
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Block B, First Floor"
              className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-white text-sm placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-white/30"
            />
          </div>
          <div className="flex items-center gap-3 pt-2">
            <button
              type="submit"
              disabled={submitting || !roomNo.trim() || !deviceName.trim()}
              className="btn-primary flex items-center gap-2 text-sm disabled:opacity-40"
            >
              {submitting && <Loader2 size={14} className="animate-spin" />}
              Create Room
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="btn-secondary text-sm"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Room List */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 size={24} className="animate-spin text-white/50" />
        </div>
      ) : rooms.length === 0 ? (
        <div className="text-center py-16">
          <MapPin size={32} className="mx-auto mb-3 text-[var(--text-tertiary)]" />
          <p className="text-[var(--text-secondary)]">No rooms configured</p>
          <p className="text-xs text-[var(--text-tertiary)] mt-1">
            Click &quot;Add Room&quot; to create your first room
          </p>
        </div>
      ) : (
        <div className="grid gap-3">
          {rooms.map((room) => (
            <div
              key={room.id}
              className="flex items-center justify-between bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-xl px-5 py-4 hover:border-[var(--border-secondary)] transition-colors"
            >
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-white/8 flex items-center justify-center">
                  <MapPin size={18} className="text-white/60" />
                </div>
                <div>
                  <div className="text-sm font-medium text-white">
                    {room.room_no}
                  </div>
                  <div className="flex items-center gap-3 mt-0.5">
                    <span className="flex items-center gap-1 text-xs text-[var(--text-tertiary)]">
                      <Cpu size={12} />
                      {room.device_name}
                    </span>
                    {room.description && (
                      <span className="flex items-center gap-1 text-xs text-[var(--text-tertiary)]">
                        <FileText size={12} />
                        {room.description}
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <button
                onClick={() => handleDelete(room)}
                className="p-2 rounded-md hover:bg-red-400/10 text-[var(--text-tertiary)] hover:text-red-400 transition-colors border-none bg-transparent"
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
