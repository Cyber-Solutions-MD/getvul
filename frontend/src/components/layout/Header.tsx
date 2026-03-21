"use client";

import { useState, useRef, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";

export default function Header() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

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
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-gray-800 bg-gray-950/80 px-6 backdrop-blur">
      <div />
      <div className="relative flex items-center gap-4" ref={ref}>
        {user && (
          <>
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
              <div className="absolute right-0 top-14 w-80 rounded-xl border border-gray-700 bg-gray-900 shadow-2xl overflow-hidden z-50">
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
