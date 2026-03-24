"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Bug,
  Cloud,
  Server,
  Users,
  Plug,
  Ticket,
  Settings,
  Shield,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/vulnerabilities", label: "Vulnerabilities", icon: Bug },
  { href: "/dashboard/cspm", label: "Cloud Posture", icon: Cloud },
  { href: "/dashboard/assets", label: "Assets", icon: Server },
  { href: "/dashboard/users", label: "Users", icon: Users },
  { href: "/dashboard/connectors", label: "Connectors", icon: Plug },
  { href: "/dashboard/tickets", label: "Tickets", icon: Ticket },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

export default function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-40 h-screen w-64 border-r border-gray-800 bg-gray-950 transition-transform duration-200",
        open ? "translate-x-0" : "-translate-x-full md:translate-x-0"
      )}
    >
      <div className="flex h-16 items-center justify-between border-b border-gray-800 px-6">
        <div className="flex items-center gap-2">
          <Shield className="h-6 w-6 text-indigo-500" />
          <span className="text-lg font-bold text-white">GetVul</span>
        </div>
        <button onClick={onClose} className="rounded-lg p-1 text-gray-400 hover:text-white md:hidden">
          <X className="h-5 w-5" />
        </button>
      </div>
      <nav className="mt-4 space-y-1 px-3">
        {nav.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onClose}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "bg-indigo-600/20 text-indigo-400"
                  : "text-gray-400 hover:bg-gray-800 hover:text-white"
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
