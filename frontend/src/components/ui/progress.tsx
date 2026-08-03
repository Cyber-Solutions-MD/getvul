"use client"

import * as React from "react"
import * as ProgressPrimitive from "@radix-ui/react-progress"

import { cn } from "@/lib/utils"

// AIE-04 (28-04) budget meter. Same "add official shadcn primitive + restyle
// with sunset tokens" precedent as tooltip.tsx (Phase 24) / textarea.tsx
// (Phase 25) -- the generated shadcn defaults reference an undefined
// "primary" color token pair, which resolves to nothing in this app (no
// such token defined) -- hence the sunset-token restyle below.
//
// Track: bg-surface-2, rounded-full -- matches the existing .switch/toggle
// track recipe (visual-language.md), per 28-UI-SPEC.md's Meter Contract.
//
// Indicator color is intentionally NOT hardcoded here: the budget meter
// needs a caller-driven SLA 3-tier fill (<75% success / 75-99% amber / >=100%
// danger, 28-UI-SPEC.md Meter Contract) -- so `indicatorClassName` overrides
// the fill color per instance. Defaults to the "ok" tier so an omitted prop
// never renders an invisible/undefined fill.
const Progress = React.forwardRef<
  React.ElementRef<typeof ProgressPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> & {
    indicatorClassName?: string
  }
>(({ className, value, indicatorClassName, ...props }, ref) => (
  <ProgressPrimitive.Root
    ref={ref}
    className={cn(
      "relative h-2 w-full overflow-hidden rounded-full bg-surface-2",
      className
    )}
    {...props}
  >
    <ProgressPrimitive.Indicator
      className={cn("h-full w-full flex-1 transition-all", indicatorClassName ?? "bg-success")}
      style={{ transform: `translateX(-${100 - (value || 0)}%)` }}
    />
  </ProgressPrimitive.Root>
))
Progress.displayName = ProgressPrimitive.Root.displayName

export { Progress }
