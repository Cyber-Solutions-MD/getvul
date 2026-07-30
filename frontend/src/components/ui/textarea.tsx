import * as React from "react"

import { cn } from "@/lib/utils"

// Phase 25 (AIR-02): restyled off the shadcn default to match the ONE
// existing free-text multi-line input in this feature area --
// ai-feedback-control.tsx's raw <textarea> (border-border-subtle/bg-surface/
// focus:border-violet) -- rather than shadcn's un-themed zinc default. No
// new hex; every color here is a sunset CSS variable already in use
// elsewhere in the app.
const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.ComponentProps<"textarea">
>(({ className, ...props }, ref) => {
  return (
    <textarea
      className={cn(
        "flex min-h-[60px] w-full resize-none rounded-md border border-border-subtle bg-surface px-3 py-2 text-sm text-text shadow-sm placeholder:text-text-faint focus:border-violet focus:outline-none focus-visible:ring-2 focus-visible:ring-violet disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      ref={ref}
      {...props}
    />
  )
})
Textarea.displayName = "Textarea"

export { Textarea }
