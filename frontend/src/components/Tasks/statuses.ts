import type { TaskPriority, TaskStatus } from "@/client"
import { type PriorityTone, priorityTone } from "./priority"

/**
 * The six statuses a task can be in, and the one list of them the interface
 * reads (FR-01.4, ADR-0008). Order is the order work moves in, with Waiting
 * beside the main road rather than on it. The controls that show and change
 * a status are in `status.tsx`.
 */
export const STATUSES = [
  "backlog",
  "todo",
  "in_progress",
  "review",
  "waiting",
  "done",
] as const satisfies readonly TaskStatus[]

/**
 * Everything that is not done: what "Open" means wherever it is offered, and
 * what the task list shows when nothing narrows it (ADR-0006).
 *
 * `OPEN_STATUS_VALUES` is the same five as a fixed vocabulary, for the
 * schema that has to accept exactly them and nothing else; `OPEN_STATUSES` is
 * the list to pass around. One source, two shapes.
 */
export const OPEN_STATUS_VALUES = [
  "backlog",
  "todo",
  "in_progress",
  "review",
  "waiting",
] as const satisfies readonly TaskStatus[]

/** An open status: everything a task can be short of done. */
export type OpenStatus = (typeof OPEN_STATUS_VALUES)[number]

export const OPEN_STATUSES: OpenStatus[] = [...OPEN_STATUS_VALUES]

export const STATUS_LABELS: Record<TaskStatus, string> = {
  backlog: "Backlog",
  todo: "To do",
  in_progress: "In progress",
  review: "Review",
  waiting: "Waiting",
  done: "Done",
}

/**
 * The colour of a status mark: the task's priority while it is open, and
 * done's green once it is closed, whatever the priority was. P4 and no
 * priority have none and stay ink.
 */
export type MarkTone = PriorityTone | "done"

export function markTone(
  status: TaskStatus,
  priority?: TaskPriority | null,
): MarkTone | null {
  return status === "done" ? "done" : priorityTone(priority)
}

/**
 * What a mark standing for a task says to assistive technology: its status,
 * and its priority, since the colour alone says nothing to a screen reader.
 */
export function markName(
  status: TaskStatus,
  priority?: TaskPriority | null,
): string {
  const label = STATUS_LABELS[status]
  return priority ? `${label}, priority ${priority}` : label
}

/**
 * The status filter as the list reads it, or nothing when it narrows nothing.
 *
 * Every open status is the list's baseline rather than a filter, so it is
 * named here as nothing at all: a chip offering to remove it would offer to
 * widen the list to something it no longer shows. A URL that spells out all
 * five reads as the baseline here; one naming the three open statuses there
 * were before Backlog and Review is a narrowing like any other (ADR-0008).
 */
export function describeStatusFilter(
  statuses: readonly TaskStatus[] | undefined,
): string | undefined {
  if (!statuses?.length) return undefined
  if (isOpenFilter(statuses)) return undefined
  return statuses.map((status) => STATUS_LABELS[status]).join(", ")
}

/** Whether this names every open status, which is what the list shows anyway. */
export function isOpenFilter(statuses: readonly TaskStatus[]): boolean {
  return (
    statuses.length === OPEN_STATUSES.length &&
    OPEN_STATUSES.every((status) => statuses.includes(status))
  )
}
