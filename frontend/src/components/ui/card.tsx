'use client';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';
import { forwardRef, type HTMLAttributes } from 'react';

// D-P-01: Card variants consume CSS variables from sunset.css via Tailwind
// tokens declared in tailwind.config.ts. No hex literals — palette contract
// enforced at acceptance (T-10-19).
const cardVariants = cva('rounded-lg border transition-colors', {
  variants: {
    variant: {
      surface: 'border-border-subtle bg-surface',
      elevated: 'border-border bg-surface-2 shadow-card',
      outline: 'border-border bg-transparent',
    },
    padding: { sm: 'p-3', md: 'p-5', lg: 'p-7' },
  },
  defaultVariants: { variant: 'surface', padding: 'md' },
});

type CardProps = HTMLAttributes<HTMLDivElement> &
  VariantProps<typeof cardVariants>;

const CardRoot = forwardRef<HTMLDivElement, CardProps>(
  ({ className, variant, padding, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(cardVariants({ variant, padding }), className)}
      {...props}
    />
  )
);
CardRoot.displayName = 'Card';

const CardHeader = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('mb-3 flex items-center justify-between', className)}
      {...props}
    />
  )
);
CardHeader.displayName = 'Card.Header';

const CardBody = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn(className)} {...props} />
  )
);
CardBody.displayName = 'Card.Body';

const CardFooter = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('mt-3 flex items-center justify-between', className)}
      {...props}
    />
  )
);
CardFooter.displayName = 'Card.Footer';

export const Card = Object.assign(CardRoot, {
  Header: CardHeader,
  Body: CardBody,
  Footer: CardFooter,
});
export type { CardProps };
