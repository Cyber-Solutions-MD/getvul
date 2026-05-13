import type { ReactNode } from 'react';
import { AppShell } from '@/components/shell/app-shell';
import ToastProvider from '@/components/ui/ToastProvider';

// Route-group layout — D-33 single chrome owner for the (authed)/ subtree.
// No route guard here; that lives in useAuth() per the chosen client-side
// redirect pattern (Phase 9 RESEARCH §"Pattern 5 — recommended pick").
// ToastProvider is hoisted from the deleted (authed)/dashboard/layout.tsx
// because multiple authed pages still consume `useToast()`.
export default function AuthedLayout({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <AppShell>{children}</AppShell>
    </ToastProvider>
  );
}
