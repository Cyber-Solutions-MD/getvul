'use client';
import * as React from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface InputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  type?: 'text' | 'email' | 'password' | 'url' | 'search' | 'tel';
}

const baseClasses =
  'block w-full bg-surface-2 border border-border-subtle rounded-md px-3 py-2 text-sm text-text ' +
  'placeholder:text-text-faint ' +
  'focus-visible:outline-none focus-visible:border-violet focus-visible:ring-2 focus-visible:ring-violet focus-visible:ring-offset-2 focus-visible:ring-offset-bg ' +
  'disabled:opacity-50 disabled:cursor-not-allowed ' +
  'aria-[invalid=true]:border-danger aria-[invalid=true]:focus-visible:border-danger aria-[invalid=true]:focus-visible:ring-danger';

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type = 'text', ...props }, ref) => {
    const [revealed, setRevealed] = React.useState(false);
    const isPassword = type === 'password';

    if (!isPassword) {
      return (
        <input
          ref={ref}
          type={type}
          className={cn(baseClasses, className)}
          {...props}
        />
      );
    }

    return (
      <div className="relative">
        <input
          ref={ref}
          type={revealed ? 'text' : 'password'}
          className={cn(baseClasses, 'pr-10', className)}
          {...props}
        />
        <button
          type="button"
          onClick={() => setRevealed((r) => !r)}
          aria-pressed={revealed}
          aria-label={revealed ? 'Hide password' : 'Show password'}
          className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded text-text-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet"
          tabIndex={0}
        >
          {revealed ? (
            <EyeOff className="h-4 w-4" aria-hidden />
          ) : (
            <Eye className="h-4 w-4" aria-hidden />
          )}
        </button>
      </div>
    );
  }
);
Input.displayName = 'Input';
