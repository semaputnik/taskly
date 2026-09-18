import { Flag } from "lucide-react"

import type { TaskPriority } from "@/client"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

/**
 * The priority hues. P4 and no priority have none: they are the ordinary
 * case, and they stay in ink as every task did before priorities had colour.
 */
export type PriorityTone = "p1" | "p2" | "p3"

export function priorityTone(
  priority: TaskPriority | null | undefined,
): PriorityTone | null {
  switch (priority) {
    case "P1":
      return "p1"
    case "P2":
      return "p2"
    case "P3":
      return "p3"
    default:
      return null
  }
}

/**
 * The priority hues as classes, written out in full so Tailwind can see them.
 * P4 and no priority have no entry: they stay in ink (the Priority Hue Rule).
 */
export const PRIORITY_TEXT: Record<PriorityTone, string> = {
  p1: "text-priority-p1",
  p2: "text-priority-p2",
  p3: "text-priority-p3",
}

/**
 * The ring and tint of the compact checkbox for each hue. The checked state
 * keeps the checkbox's own teal: done is done, whatever the priority was.
 */
export const PRIORITY_CHECK: Record<PriorityTone, string> = {
  p1: "border-priority-p1 bg-priority-p1/10 dark:bg-priority-p1/15",
  p2: "border-priority-p2 bg-priority-p2/10 dark:bg-priority-p2/15",
  p3: "border-priority-p3 bg-priority-p3/10 dark:bg-priority-p3/15",
}

const PRIORITY_BADGE: Record<PriorityTone, string> = {
  p1: "text-priority-p1 border-priority-p1/40",
  p2: "text-priority-p2 border-priority-p2/40",
  p3: "text-priority-p3 border-priority-p3/40",
}

/** A priority as the metadata pill it has always been, in its hue. */
export function PriorityBadge({
  priority,
  className,
}: {
  priority: TaskPriority
  className?: string
}) {
  const tone = priorityTone(priority)
  return (
    <Badge
      variant="outline"
      className={cn(tone && PRIORITY_BADGE[tone], className)}
    >
      {priority}
    </Badge>
  )
}

/**
 * A priority as a choice in a menu: its flag in its hue beside its name, so
 * the colour is learnt where the priority is set.
 */
export function PriorityOption({ priority }: { priority: TaskPriority }) {
  const tone = priorityTone(priority)
  return (
    <span className="flex items-center gap-2">
      <Flag
        className={cn("size-3.5 shrink-0", tone && PRIORITY_TEXT[tone])}
        aria-hidden
      />
      {priority}
    </span>
  )
}
