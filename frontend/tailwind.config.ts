import type { Config } from 'tailwindcss';
import tailwindcssAnimate from 'tailwindcss-animate';

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        // Surfaces (D-09)
        bg:           'var(--color-bg)',
        'bg-darker':  'var(--color-bg-darker)',
        surface:         'var(--color-surface)',
        'surface-2':     'var(--color-surface-2)',
        'surface-glass': 'var(--color-surface-glass)',
        // Borders
        border:           'var(--color-border)',
        'border-subtle':  'var(--color-border-subtle)',
        'border-strong':  'var(--color-border-strong)',
        // Text
        text:           'var(--color-text)',
        'text-muted':   'var(--color-text-muted)',
        'text-faint':   'var(--color-text-faint)',
        'text-inverse': 'var(--color-text-inverse)',
        // Sunset accents
        pink:          'var(--color-pink)',
        'pink-soft':   'var(--color-pink-soft)',
        violet:        'var(--color-violet)',
        'violet-soft': 'var(--color-violet-soft)',
        amber:         'var(--color-amber)',
        'amber-soft':  'var(--color-amber-soft)',
        // Semantic states
        danger:        'var(--color-danger)',
        'danger-soft': 'var(--color-danger-soft)',
        success:       'var(--color-success)',
        'success-soft':'var(--color-success-soft)',
        warning:       'var(--color-warning)',
        info:          'var(--color-info)',
        // Severity tokens (D-10)
        'severity-critical': 'var(--color-severity-critical)',
        'severity-high':     'var(--color-severity-high)',
        'severity-medium':   'var(--color-severity-medium)',
        'severity-low':      'var(--color-severity-low)',
        'severity-info':     'var(--color-severity-info)',
        // Status tokens (D-10) — even though no Phase 9 consumer
        'status-open':       'var(--color-violet)',
        'status-inprogress': 'var(--color-amber)',
        'status-completed':  'var(--color-success)',
        'status-blocked':    'var(--color-danger)',
        // SLA tokens (D-10)
        'sla-overdue': 'var(--color-severity-critical)',
        'sla-soon':    'var(--color-severity-high)',
        'sla-ok':      'var(--color-success)',
        // Provider gradient marks (D-10) — phase 13 consumer
        'provider-jira':   '#5C9CFF',
        'provider-asana':  '#FF8AA0',
        'provider-github': 'var(--color-violet)',
      },
      backgroundImage: {
        'gradient-sunset':          'var(--gradient-sunset)',
        'gradient-sunset-vertical': 'var(--gradient-sunset-vertical)',
        'gradient-mesh':            'var(--gradient-mesh)',
        'gradient-orb':             'var(--gradient-orb)',
      },
      fontFamily: {
        sans: ['var(--font-sans)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'monospace'],
      },
      borderRadius: {
        sm:    'var(--radius-sm)',
        md:    'var(--radius-md)',
        lg:    'var(--radius-lg)',
        xl:    'var(--radius-xl)',
        '2xl': 'var(--radius-2xl)',
      },
      boxShadow: {
        card:          'var(--shadow-card)',
        elevated:      'var(--shadow-elevated)',
        'glow-pink':   'var(--glow-pink)',
        'glow-violet': 'var(--glow-violet)',
        'glow-amber':  'var(--glow-amber)',
        'glow-cta':    'var(--glow-cta)',
      },
      keyframes: {
        'pulse-urgency':     { '0%, 100%': { boxShadow: '0 0 0 0 rgba(248, 113, 113, 0.6)' }, '50%': { boxShadow: '0 0 0 8px rgba(248, 113, 113, 0)' } },
        'gradient-drift':    { '0%, 100%': { transform: 'scale(1) translate(0, 0)' }, '50%': { transform: 'scale(1.1) translate(-2%, 1%)' } },
        'skeleton-shimmer':  { from: { backgroundPosition: '200% 0' }, to: { backgroundPosition: '-200% 0' } },
        'cta-shine-sweep':   { '0%': { transform: 'translateX(-100%)' }, '100%': { transform: 'translateX(100%)' } },
      },
      animation: {
        'pulse-urgency':    'pulse-urgency 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'gradient-drift':   'gradient-drift 24s ease-in-out infinite',
        'skeleton-shimmer': 'skeleton-shimmer 2s linear infinite',
        'shimmer':          'skeleton-shimmer 1.6s linear infinite', // Phase 11 SkeletonTable alias (state-patterns.md timing)
        'cta-shine-sweep':  'cta-shine-sweep 3s ease-in-out infinite',
      },
    },
  },
  plugins: [tailwindcssAnimate],  // D-16: NO @tailwindcss/forms, NO @tailwindcss/typography. tailwindcss-animate added by Wave 1 — shadcn-generated DropdownMenu animation classes (data-[state=open]:animate-in, fade-out-0, zoom-out-95, slide-in-from-top-2, etc.) require it.
};

export default config;
