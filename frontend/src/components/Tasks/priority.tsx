import { Flag } from "lucide-react"

import type { TaskPriority } from "@/client"
import { cn } from "@/lib/utils"
import { type PriorityTone, priorityTone } from "./priorityTone"

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
 * A priority as the value of its property row: the flag and the label in the
 * priority's hue, medium weight; P4 stays in ink, and no priority is said in
 * the quiet grey of every unset value.
 */
export function PriorityValue({
  priority,
}: {
  priority: TaskPriority | null | undefined
}) {
  if (!priority) {
    return <span className="text-muted-foreground">No priority</span>
  }
  const tone = priorityTone(priority)
  return (
    <span
      className={cn(
        "flex items-center gap-1.5 font-medium",
        tone ? PRIORITY_TEXT[tone] : "text-foreground",
      )}
    >
      {/* `text-current` keeps the select trigger's grey off the flag. */}
      <Flag
        className="size-3.5 shrink-0 fill-current text-current"
        aria-hidden
      />
      {priority}
    </span>
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
