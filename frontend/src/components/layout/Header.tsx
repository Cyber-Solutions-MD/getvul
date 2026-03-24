"use client";

import { useState, useRef, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { Bell, Menu } from "lucide-react";

function timeAgo(iso: string): string {
  const diffMin = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHrs = Math.floor(diffMin / 60);
  if (diffHrs < 24) return `${diffHrs}h ago`;
  return `${Math.floor(diffHrs / 24)}d ago`;
}

export default function Header({ onMenuToggle }: { onMenuToggle?: () => void }) {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Notification bell state
  const [notifOpen, setNotifOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [notifLoading, setNotifLoading] = useState(false);
  const notifRef = useRef<HTMLDivElement>(null);

  // Poll unread count
  useEffect(() => {
    const fetchCount = () => {
      api("/api/v1/notifications/unread-count").then(d => setUnreadCount(d.count || 0)).catch(() => {});
    };
    fetchCount();
    const interval = setInterval(fetchCount, 30000);
    return () => clearInterval(interval);
  }, []);

  // Load notifications when panel opens
  useEffect(() => {
    if (notifOpen) {
      setNotifLoading(true);
      api("/api/v1/notifications?page_size=15").then(d => setNotifications(d.items || [])).catch(() => {}).finally(() => setNotifLoading(false));
    }
  }, [notifOpen]);

  // Close notification panel on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) setNotifOpen(false);
    }
    if (notifOpen) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [notifOpen]);

  const markRead = async (id: string) => {
    await api(`/api/v1/notifications/${id}/read`, { method: "POST" });
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
    setUnreadCount(c => Math.max(0, c - 1));
  };

  const markAllRead = async () => {
    await api("/api/v1/notifications/read-all", { method: "POST" });
    setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
    setUnreadCount(0);
  };

  const initials = user?.display_name
    ? user.display_name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2)
    : user?.email?.[0]?.toUpperCase() || "?";

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-gray-800 bg-gray-950/80 px-4 md:px-6 backdrop-blur">
      <button onClick={onMenuToggle} className="rounded-lg p-1.5 text-gray-400 hover:text-white md:hidden">
        <Menu className="h-5 w-5" />
      </button>
      <div className="hidden md:block" />
      <div className="relative flex items-center gap-4" ref={ref}>
        {user && (
          <>
            {/* Notification bell */}
            <div className="relative" ref={notifRef}>
              <button onClick={() => setNotifOpen(!notifOpen)} className="relative p-1.5 rounded-lg hover:bg-gray-800 transition">
                <Bell className="h-5 w-5 text-gray-400" />
                {unreadCount > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
                    {unreadCount > 9 ? "9+" : unreadCount}
                  </span>
                )}
              </button>

              {notifOpen && (
                <div className="absolute right-0 top-full mt-2 w-[calc(100vw-2rem)] sm:w-96 rounded-xl border border-gray-700 bg-gray-900 shadow-2xl z-50 max-h-[500px] overflow-hidden">
                  {/* Header */}
                  <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
                    <h3 className="text-sm font-semibold text-white">Notifications</h3>
                    {unreadCount > 0 && (
                      <button onClick={markAllRead} className="text-xs text-indigo-400 hover:text-indigo-300">Mark all read</button>
                    )}
                  </div>

                  {/* List */}
                  <div className="overflow-y-auto max-h-[420px] divide-y divide-gray-800">
                    {notifLoading ? (
                      <p className="text-center text-gray-500 text-sm py-8">Loading...</p>
                    ) : notifications.length === 0 ? (
                      <p className="text-center text-gray-500 text-sm py-8">No notifications</p>
                    ) : notifications.map(n => (
                      <div key={n.id} onClick={() => !n.is_read && markRead(n.id)}
                        className={`px-4 py-3 cursor-pointer transition ${n.is_read ? "opacity-60" : "hover:bg-gray-800/50"}`}>
                        <div className="flex items-start gap-2">
                          <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${
                            n.severity === "critical" ? "bg-red-500" :
                            n.severity === "high" ? "bg-orange-500" :
                            n.severity === "medium" ? "bg-yellow-500" : "bg-blue-500"
                          }`} />
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-white truncate">{n.title}</p>
                            <p className="text-xs text-gray-400 mt-0.5 line-clamp-2">{n.message}</p>
                            <p className="text-[10px] text-gray-600 mt-1">{timeAgo(n.created_at)}</p>
                          </div>
                          {!n.is_read && <span className="h-2 w-2 shrink-0 rounded-full bg-indigo-500 mt-1.5" />}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <button onClick={() => setOpen(!open)} className="flex items-center gap-3 rounded-lg px-2 py-1.5 hover:bg-gray-800 transition">
              <div className="text-right hidden sm:block">
                <p className="text-sm font-medium text-white">{user.display_name || user.email}</p>
                <p className="text-xs text-gray-500">{user.role}</p>
              </div>
              <div className="h-8 w-8 rounded-full bg-indigo-600 flex items-center justify-center text-xs font-bold text-white">
                {initials}
              </div>
            </button>

            {open && (
              <div className="absolute right-0 top-14 w-[calc(100vw-2rem)] sm:w-80 rounded-xl border border-gray-700 bg-gray-900 shadow-2xl overflow-hidden z-50">
                {/* Account info */}
                <div className="border-b border-gray-800 px-5 py-4">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full bg-indigo-600 flex items-center justify-center text-sm font-bold text-white shrink-0">
                      {initials}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-white truncate">{user.display_name || user.email}</p>
                      <p className="text-xs text-gray-500 truncate">{user.email}</p>
                      <p className="text-xs text-indigo-400 mt-0.5">{user.role}</p>
                    </div>
                  </div>
                </div>

                {/* Change password */}
                <div className="px-5 py-3 border-b border-gray-800">
                  <ChangePasswordInline />
                </div>

                {/* Logout */}
                <div className="px-5 py-3">
                  <button onClick={logout}
                    className="w-full rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-400 hover:text-white hover:border-gray-500 transition">
                    Logout
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </header>
  );
}

function ChangePasswordInline() {
  const [editing, setEditing] = useState(false);
  const [current, setCurrent] = useState("");
  const [newPass, setNewPass] = useState("");
  const [msg, setMsg] = useState("");
  const [saving, setSaving] = useState(false);

  if (!editing) {
    return (
      <button onClick={() => setEditing(true)}
        className="text-sm text-indigo-400 hover:text-indigo-300 transition">
        Change password
      </button>
    );
  }

  return (
    <div className="space-y-2">
      <input type="password" value={current} onChange={e => setCurrent(e.target.value)}
        placeholder="Current password"
        className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none" />
      <input type="password" value={newPass} onChange={e => setNewPass(e.target.value)}
        placeholder="New password (min 8 chars)"
        className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none" />
      {msg && <p className={`text-xs ${msg.startsWith("Error") ? "text-red-400" : "text-emerald-400"}`}>{msg}</p>}
      <div className="flex gap-2">
        <button onClick={async () => {
          setSaving(true); setMsg("");
          try {
            await api("/auth/change-password", {
              method: "POST",
              body: JSON.stringify({ current_password: current || null, new_password: newPass }),
            });
            setMsg("Password updated");
            setCurrent(""); setNewPass("");
            setTimeout(() => setEditing(false), 1500);
          } catch (e: any) { setMsg(`Error: ${e.message}`); } finally { setSaving(false); }
        }} disabled={newPass.length < 8 || saving}
          className="rounded-lg bg-indigo-600 px-3 py-1 text-xs text-white hover:bg-indigo-500 disabled:opacity-50">
          {saving ? "Saving..." : "Update"}
        </button>
        <button onClick={() => { setEditing(false); setMsg(""); setCurrent(""); setNewPass(""); }}
          className="text-xs text-gray-500 hover:text-gray-300">Cancel</button>
      </div>
    </div>
  );
}
