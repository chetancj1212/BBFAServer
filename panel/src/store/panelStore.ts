import { create } from "zustand";
import type { Admin, Room, ClassInfo, ActiveSession } from "@/types";

interface PanelState {
  /* Auth */
  admin: Admin | null;
  isAuthenticated: boolean;
  login: (admin: Admin) => void;
  logout: () => void;

  /* Navigation */
  currentView: "dashboard" | "start-class" | "live-session" | "history" | "manage-rooms" | "manage-classes";
  setView: (view: PanelState["currentView"]) => void;

  /* Rooms & Classes */
  rooms: Room[];
  classes: ClassInfo[];
  setRooms: (rooms: Room[]) => void;
  setClasses: (classes: ClassInfo[]) => void;

  /* Active session */
  activeSession: ActiveSession | null;
  setActiveSession: (session: ActiveSession | null) => void;
}

export const usePanelStore = create<PanelState>((set) => ({
  admin: null,
  isAuthenticated: false,
  login: (admin) => set({ admin, isAuthenticated: true }),
  logout: () =>
    set({
      admin: null,
      isAuthenticated: false,
      currentView: "dashboard",
      activeSession: null,
    }),

  currentView: "dashboard",
  setView: (view) => set({ currentView: view }),

  rooms: [],
  classes: [],
  setRooms: (rooms) => set({ rooms }),
  setClasses: (classes) => set({ classes }),

  activeSession: null,
  setActiveSession: (session) => set({ activeSession: session }),
}));
