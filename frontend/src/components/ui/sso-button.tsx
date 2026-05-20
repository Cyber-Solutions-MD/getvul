'use client';
import * as React from 'react';
import { cn } from '@/lib/utils';
import { GoogleIcon, MicrosoftIcon } from './sso-icons';

export type SsoProvider = 'google' | 'microsoft';

const PROVIDER_LABEL: Record<SsoProvider, string> = {
  google: 'Continue with Google',
  microsoft: 'Continue with Microsoft',
};

const PROVIDER_ICON: Record<
  SsoProvider,
  React.ComponentType<React.SVGProps<SVGSVGElement>>
> = {
  google: GoogleIcon,
  microsoft: MicrosoftIcon,
};

export interface SsoButtonProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  provider: SsoProvider;
}

export const SsoButton = React.forwardRef<HTMLButtonElement, SsoButtonProps>(
  ({ provider, className, ...props }, ref) => {
    const Icon = PROVIDER_ICON[provider];
    const label = PROVIDER_LABEL[provider];
    return (
      <button
        ref={ref}
        type="button"
        className={cn(
          'flex w-full items-center justify-center gap-2.5 rounded-md',
          'border border-border bg-surface-2 px-4 py-2.5 text-sm font-medium text-text',
          'transition-all hover:-translate-y-px hover:border-border-strong hover:bg-surface',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet focus-visible:ring-offset-2 focus-visible:ring-offset-bg',
          'disabled:pointer-events-none disabled:opacity-50',
          className
        )}
        aria-label={label}
        {...props}
      >
        <Icon aria-hidden />
        <span>{label}</span>
      </button>
    );
  }
);
SsoButton.displayName = 'SsoButton';
