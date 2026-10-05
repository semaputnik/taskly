import type { TaskPriority } from "@/client"

/*
 * Free of React, lucide and components on purpose: Playwright specs import
 * this (through `statuses.ts`) to stay in step with the app, and a spec that
 * loads React in Playwright's Node runner fails to load at all. The icons and
 * badges built on these tones are in `priority.tsx`.
 */

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
