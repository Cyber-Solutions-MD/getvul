import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';

export interface GradientTextProps extends React.HTMLAttributes<HTMLElement> {
  asChild?: boolean;
}

const gradientStyle: React.CSSProperties = {
  background: 'var(--gradient-sunset)',
  backgroundClip: 'text',
  WebkitBackgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
  color: 'transparent',
};

export const GradientText = React.forwardRef<HTMLElement, GradientTextProps>(
  ({ asChild = false, className, style, children, ...props }, ref) => {
    const Comp: React.ElementType = asChild ? Slot : 'span';
    return (
      <Comp
        ref={ref}
        className={className}
        style={{ ...gradientStyle, ...style }}
        {...props}
      >
        {children}
      </Comp>
    );
  }
);
GradientText.displayName = 'GradientText';
