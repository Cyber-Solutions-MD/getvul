'use client';
import { useAuth } from '@/lib/auth';
import { useTheme } from '@/lib/theme';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
} from '@/components/ui/dropdown-menu';
import { LogOut, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

function initials(email?: string | null): string {
  if (!email) return '?';
  const [local] = email.split('@');
  // 2-letter from the local part — e.g. "igor.chen" -> "IC"; "admin" -> "AD"
  const parts = local.split(/[._-]+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return local.slice(0, 2).toUpperCase();
}

export function UserChip() {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();

  if (!user) return null;  // not authed — shell shouldn't render anyway, defensive

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Account menu"
        className={cn(
          'flex items-center gap-2 rounded-md border border-border-subtle bg-surface px-2 py-1.5',
          'text-sm text-text hover:bg-surface-2',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet focus-visible:ring-offset-2 focus-visible:ring-offset-bg',
          'data-[state=open]:bg-surface-2'
        )}
      >
        <span
          aria-hidden
          className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-sunset text-[11px] font-semibold text-white"
        >
          {initials(user.email)}
        </span>
        <ChevronDown className="h-3.5 w-3.5 text-text-faint" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[220px]">
        <DropdownMenuLabel className="text-xs font-normal text-text-muted">
          {user.email}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />

        {/* Theme radio per D-38. Both dark and light themes shipped in Phase 16
            (UX-D-03) — all severity, accent, danger, and glow tokens pass the
            axe WCAG 2.1 AA gate on both surfaces. */}
        <DropdownMenuRadioGroup
          value={theme}
          onValueChange={(v) => setTheme(v as 'dark' | 'light')}
        >
          <DropdownMenuRadioItem value="dark">{'Theme: Dark'}</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="light">{'Theme: Light'}</DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>

        <DropdownMenuSeparator />

        <DropdownMenuItem
          onSelect={() => {
            void logout();
          }}
          className="text-text"
        >
          <LogOut className="mr-2 h-4 w-4" aria-hidden />
          {'Sign out'}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
