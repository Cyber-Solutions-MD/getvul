"use client";

import { useAuth } from "@/lib/auth";

export default function Header() {
  const { user, logout } = useAuth();

  const initials = user?.display_name
    ? user.display_name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2)
    : user?.email?.[0]?.toUpperCase() || "?";

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-gray-800 bg-gray-950/80 px-6 backdrop-blur">
      <div />
      <div className="flex items-center gap-4">
        {user && (
          <>
            <div className="text-right hidden sm:block">
              <p className="text-sm font-medium text-white">{user.display_name || user.email}</p>
              <p className="text-xs text-gray-500">{user.role}</p>
            </div>
            <div className="h-8 w-8 rounded-full bg-indigo-600 flex items-center justify-center text-xs font-bold text-white">
              {initials}
            </div>
            <button onClick={logout}
              className="rounded-lg border border-gray-700 px-3 py-1.5 text-xs text-gray-400 hover:text-white hover:border-gray-500 transition">
              Logout
            </button>
          </>
        )}
      </div>
    </header>
  );
}
