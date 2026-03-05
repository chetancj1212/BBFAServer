"use client";

import { useEffect, useState } from "react";
import { usePanelStore } from "@/store/panelStore";
import { Wifi, WifiOff } from "lucide-react";
import LoginCard from "@/components/auth/LoginCard";
import Dashboard from "@/components/dashboard/Dashboard";
import StartClass from "@/components/session/StartClass";
import LiveSession from "@/components/session/LiveSession";
import History from "@/components/history/History";
import ManageRooms from "@/components/manage/ManageRooms";
import ManageClasses from "@/components/manage/ManageClasses";

export default function PanelApp() {
  const { isAuthenticated, currentView } = usePanelStore();

  if (!isAuthenticated) {
    return <LoginCard />;
  }

  return (
    <div className="min-h-screen bg-black flex flex-col">
      <AppHeader />
      <main className="flex-1 p-6 max-w-6xl mx-auto w-full animate-fade-in">
        {currentView === "dashboard" && <Dashboard />}
        {currentView === "start-class" && <StartClass />}
        {currentView === "live-session" && <LiveSession />}
        {currentView === "history" && <History />}
        {currentView === "manage-rooms" && <ManageRooms />}
        {currentView === "manage-classes" && <ManageClasses />}
      </main>
    </div>
  );
}

function AppHeader() {
  const { admin, logout, currentView, setView } = usePanelStore();
  const [backendOnline, setBackendOnline] = useState(false);

  useEffect(() => {
    const check = () => fetch("/api-backend/").then(r => setBackendOnline(r.ok)).catch(() => setBackendOnline(false));
    check();
    const id = setInterval(check, 30000);
    return () => clearInterval(id);
  }, []);

  const navItems: { key: typeof currentView; label: string; icon: string }[] = [
    { key: "dashboard", label: "Dashboard", icon: "fa-solid fa-grid-2" },
    { key: "manage-rooms", label: "Rooms", icon: "fa-solid fa-door-open" },
    { key: "manage-classes", label: "Classes", icon: "fa-solid fa-chalkboard-user" },
    { key: "start-class", label: "Start Class", icon: "fa-solid fa-play" },
    { key: "history", label: "History", icon: "fa-solid fa-clock-rotate-left" },
  ];

  return (
    <header className="sticky top-0 z-50 border-b border-[var(--border-primary)] bg-black/80 backdrop-blur-md">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <span className="text-base font-semibold tracking-tight text-white">
            Admin
          </span>
        </div>

        {/* Nav */}
        <nav className="flex items-center gap-1">
          {navItems.map((item) => (
            <button
              key={item.key}
              onClick={() => setView(item.key)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-all border-none ${
                currentView === item.key
                  ? "bg-white/10 text-white"
                  : "text-[var(--text-secondary)] hover:text-white hover:bg-white/5"
              }`}
            >
              <i className={`${item.icon} text-xs`} />
              <span className="hidden sm:inline">{item.label}</span>
            </button>
          ))}
        </nav>

        {/* Status + User */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-2 py-1 rounded-md">
            {backendOnline ? (
              <Wifi className="w-3 h-3 text-emerald-400" />
            ) : (
              <WifiOff className="w-3 h-3 text-red-400" />
            )}
          </div>
          <span className="text-sm text-[var(--text-secondary)] hidden sm:inline">
            {admin?.name || admin?.unique_id}
          </span>
          <button
            onClick={logout}
            className="text-xs text-[var(--text-tertiary)] hover:text-red-400 transition-colors border-none bg-transparent px-2 py-1"
          >
            <i className="fa-solid fa-right-from-bracket" />
          </button>
        </div>
      </div>
    </header>
  );
}
