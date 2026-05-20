import { AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';

// Auth-form-level error banner (D-28, UX-01-05). One-off, not a primitive —
// lives in components/auth/ alongside future password-strength / mfa-prompt
// pieces. Uses bg-danger-soft + border-danger + text-danger so the banner
// reads as "form error" not "destructive action".
export interface ErrorAlertProps {
  children: React.ReactNode;
  className?: string;
}

export function ErrorAlert({ children, className }: ErrorAlertProps) {
  return (
    <div
      role="alert"
      className={cn(
        'flex items-start gap-2 rounded-md border border-danger bg-danger-soft px-3 py-2.5 text-sm text-danger',
        className,
      )}
    >
      <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" aria-hidden />
      <span>{children}</span>
    </div>
  );
}
