"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { Bell, Menu, Sun, Moon, Search, Loader2 } from "lucide-react";
import { useTheme } from "@/lib/theme";
import { useRouter } from "next/navigation";

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
  const { theme, toggle: toggleTheme } = useTheme();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Record<string, any[]>>({});
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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

  // Debounced search fetch
  const fetchSearch = useCallback((q: string) => {
    if (q.length < 2) { setSearchResults({}); setSearchOpen(false); return; }
    setSearchLoading(true);
    setSearchOpen(true);
    api(`/api/v1/search?q=${encodeURIComponent(q)}&limit=5`)
      .then((data) => {
        const grouped: Record<string, any[]> = {};
        if (data.vulnerabilities?.length) grouped["Vulnerabilities"] = data.vulnerabilities;
        if (data.assets?.length) grouped["Assets"] = data.assets;
        if (data.users?.length) grouped["Users"] = data.users;
        if (data.tickets?.length) grouped["Tickets"] = data.tickets;
        if (data.cspm?.length) grouped["CSPM"] = data.cspm;
        setSearchResults(grouped);
      })
      .catch(() => setSearchResults({}))
      .finally(() => setSearchLoading(false));
  }, []);

  const handleSearchInput = (value: string) => {
    setSearchQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchSearch(value), 300);
  };

  // Close search on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setSearchOpen(false);
        setMobileSearchOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Keyboard shortcut: `/` or Cmd+K to focus search
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") { setSearchOpen(false); setMobileSearchOpen(false); return; }
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.key === "/" || (e.metaKey && e.key === "k")) {
        e.preventDefault();
        setMobileSearchOpen(true);
        setTimeout(() => searchInputRef.current?.focus(), 50);
      }
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, []);

  const navigateResult = (category: string, item: any) => {
    setSearchOpen(false);
    setMobileSearchOpen(false);
    setSearchQuery("");
    setSearchResults({});
    switch (category) {
      case "Vulnerabilities":
        router.push(`/dashboard/vulnerabilities?search=${encodeURIComponent(item.cve_id || "")}`);
        break;
      case "Assets":
        router.push(`/dashboard/assets/${item.id}`);
        break;
      case "Users":
        router.push(`/dashboard/users?search=${encodeURIComponent(item.name || item.email || "")}`);
        break;
      case "Tickets":
        router.push("/dashboard/tickets");
        break;
      case "CSPM":
        router.push("/dashboard/cspm");
        break;
    }
  };

  const severityBadge = (sev: string) => {
    const colors: Record<string, string> = {
      critical: "bg-red-500/20 text-red-400",
      high: "bg-orange-500/20 text-orange-400",
      medium: "bg-yellow-500/20 text-yellow-400",
      low: "bg-blue-500/20 text-blue-400",
      info: "bg-gray-500/20 text-gray-400",
    };
    return colors[sev?.toLowerCase()] || "bg-gray-500/20 text-gray-400";
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

      {/* Global search */}
      <div className="flex-1 flex justify-center px-2 md:px-4" ref={searchRef}>
        {/* Desktop: always-visible search input */}
        <div className="hidden md:block relative w-96">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
          <input
            ref={searchInputRef}
            type="text"
            value={searchQuery}
            onChange={(e) => handleSearchInput(e.target.value)}
            placeholder="Search vulns, assets, users..."
            className="w-full rounded-lg border border-gray-700 bg-gray-800 py-2 pl-10 pr-10 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none transition"
          />
          {searchQuery && (
            <button onClick={() => { setSearchQuery(""); setSearchResults({}); setSearchOpen(false); }} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 text-xs">
              ESC
            </button>
          )}
          {/* Desktop results dropdown */}
          {searchOpen && (
            <div className="absolute left-0 top-full mt-2 w-96 rounded-xl border border-gray-700 bg-gray-900 shadow-2xl z-50 max-h-[420px] overflow-y-auto">
              {searchLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
                </div>
              ) : Object.keys(searchResults).length === 0 ? (
                <p className="text-center text-gray-500 text-sm py-8">No results</p>
              ) : (
                Object.entries(searchResults).map(([category, items]) => (
                  <div key={category}>
                    <div className="px-4 py-2 text-xs text-gray-500 uppercase font-semibold tracking-wider">{category}</div>
                    {items.map((item, i) => (
                      <button
                        key={i}
                        onClick={() => navigateResult(category, item)}
                        className="w-full text-left px-4 py-2 hover:bg-gray-800 transition flex items-center gap-2 min-w-0"
                      >
                        {category === "Vulnerabilities" && (
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            <span className="text-sm font-semibold text-white truncate">{item.cve_id}</span>
                            <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium ${severityBadge(item.severity)}`}>{item.severity}</span>
                            <span className="text-xs text-gray-400 truncate">{item.hostname}</span>
                            <span className="text-xs text-gray-500 truncate">{item.product}</span>
                          </div>
                        )}
                        {category === "Assets" && (
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            <span className="text-sm font-semibold text-white truncate">{item.hostname}</span>
                            <span className="text-xs text-gray-400 truncate">{item.os}</span>
                            {item.risk_score != null && <span className="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium bg-indigo-500/20 text-indigo-400">{item.risk_score}</span>}
                            <span className="text-xs text-gray-500 truncate">{item.category}</span>
                          </div>
                        )}
                        {category === "Users" && (
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            <span className="text-sm font-semibold text-white truncate">{item.name}</span>
                            <span className="text-xs text-gray-400 truncate">{item.email}</span>
                            <span className="text-xs text-gray-500 truncate">{item.department}</span>
                            <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium ${item.status === "active" ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>{item.status}</span>
                          </div>
                        )}
                        {category === "Tickets" && (
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            <span className="text-sm font-semibold text-white truncate">{item.cve_id}</span>
                            {item.provider && <span className="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium bg-purple-500/20 text-purple-400">{item.provider}</span>}
                            <span className="text-xs text-gray-400 truncate">{item.status}</span>
                          </div>
                        )}
                        {category === "CSPM" && (
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            <span className="text-sm font-semibold text-white truncate">{item.rule_name}</span>
                            <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium ${severityBadge(item.severity)}`}>{item.severity}</span>
                            <span className="text-xs text-gray-400 truncate">{item.resource}</span>
                            <span className="text-xs text-gray-500 truncate">{item.cloud_provider}</span>
                          </div>
                        )}
                      </button>
                    ))}
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* Mobile: icon button that expands to full-width input */}
        <div className="md:hidden relative">
          {!mobileSearchOpen ? (
            <button onClick={() => { setMobileSearchOpen(true); setTimeout(() => searchInputRef.current?.focus(), 50); }} className="rounded-lg p-1.5 text-gray-400 hover:text-white">
              <Search className="h-5 w-5" />
            </button>
          ) : (
            <div className="fixed inset-x-0 top-0 z-50 flex items-center gap-2 border-b border-gray-800 bg-gray-950 px-4 h-16">
              <Search className="h-4 w-4 text-gray-500 shrink-0" />
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => handleSearchInput(e.target.value)}
                placeholder="Search vulns, assets, users..."
                className="flex-1 rounded-lg border border-gray-700 bg-gray-800 py-2 pl-3 pr-3 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none transition"
              />
              <button onClick={() => { setMobileSearchOpen(false); setSearchOpen(false); setSearchQuery(""); setSearchResults({}); }} className="text-sm text-gray-400 hover:text-white shrink-0">
                Cancel
              </button>
              {/* Mobile results dropdown */}
              {searchOpen && (
                <div className="absolute left-4 right-4 top-full mt-2 rounded-xl border border-gray-700 bg-gray-900 shadow-2xl z-50 max-h-[420px] overflow-y-auto">
                  {searchLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
                    </div>
                  ) : Object.keys(searchResults).length === 0 ? (
                    <p className="text-center text-gray-500 text-sm py-8">No results</p>
                  ) : (
                    Object.entries(searchResults).map(([category, items]) => (
                      <div key={category}>
                        <div className="px-4 py-2 text-xs text-gray-500 uppercase font-semibold tracking-wider">{category}</div>
                        {items.map((item, i) => (
                          <button
                            key={i}
                            onClick={() => navigateResult(category, item)}
                            className="w-full text-left px-4 py-2 hover:bg-gray-800 transition flex items-center gap-2 min-w-0"
                          >
                            {category === "Vulnerabilities" && (
                              <div className="flex items-center gap-2 min-w-0 flex-1">
                                <span className="text-sm font-semibold text-white truncate">{item.cve_id}</span>
                                <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium ${severityBadge(item.severity)}`}>{item.severity}</span>
                                <span className="text-xs text-gray-400 truncate">{item.hostname}</span>
                              </div>
                            )}
                            {category === "Assets" && (
                              <div className="flex items-center gap-2 min-w-0 flex-1">
                                <span className="text-sm font-semibold text-white truncate">{item.hostname}</span>
                                <span className="text-xs text-gray-400 truncate">{item.os}</span>
                                {item.risk_score != null && <span className="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium bg-indigo-500/20 text-indigo-400">{item.risk_score}</span>}
                              </div>
                            )}
                            {category === "Users" && (
                              <div className="flex items-center gap-2 min-w-0 flex-1">
                                <span className="text-sm font-semibold text-white truncate">{item.name}</span>
                                <span className="text-xs text-gray-400 truncate">{item.email}</span>
                              </div>
                            )}
                            {category === "Tickets" && (
                              <div className="flex items-center gap-2 min-w-0 flex-1">
                                <span className="text-sm font-semibold text-white truncate">{item.cve_id}</span>
                                <span className="text-xs text-gray-400 truncate">{item.status}</span>
                              </div>
                            )}
                            {category === "CSPM" && (
                              <div className="flex items-center gap-2 min-w-0 flex-1">
                                <span className="text-sm font-semibold text-white truncate">{item.rule_name}</span>
                                <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium ${severityBadge(item.severity)}`}>{item.severity}</span>
                              </div>
                            )}
                          </button>
                        ))}
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="relative flex items-center gap-4" ref={ref}>
        {user && (
          <>
            {/* Theme toggle */}
            <button onClick={toggleTheme} className="p-1.5 rounded-lg hover:bg-gray-800 transition" title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}>
              {theme === "dark" ? <Sun className="h-5 w-5 text-gray-400" /> : <Moon className="h-5 w-5 text-gray-400" />}
            </button>

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
