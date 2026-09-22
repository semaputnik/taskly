import type { TaskStatus } from "@/client"

/**
 * The four statuses a task can be in, and the one list of them the interface
 * reads (FR-01.4). Order is the order work moves in. The controls that show
 * and change a status are in `status.tsx`.
 */
export const STATUSES = [
  "todo",
  "in_progress",
  "waiting",
  "done",
] as const satisfies readonly TaskStatus[]

/**
 * Everything that is not done: what "Open" means wherever it is offered, and
 * what the task list shows when nothing narrows it (ADR-0006).
 *
 * `OPEN_STATUS_VALUES` is the same three as a fixed vocabulary, for the
 * schema that has to accept exactly them and nothing else; `OPEN_STATUSES` is
 * the list to pass around. One source, two shapes.
 */
export const OPEN_STATUS_VALUES = [
  "todo",
  "in_progress",
  "waiting",
] as const satisfies readonly TaskStatus[]

/** An open status: everything a task can be short of done. */
export type OpenStatus = (typeof OPEN_STATUS_VALUES)[number]

export const OPEN_STATUSES: OpenStatus[] = [...OPEN_STATUS_VALUES]

export const STATUS_LABELS: Record<TaskStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  waiting: "Waiting",
  done: "Done",
}

/**
 * The status filter as the list reads it, or nothing when it narrows nothing.
 *
 * Every open status is the list's baseline rather than a filter, so it is
 * named here as nothing at all: a chip offering to remove it would offer to
 * widen the list to something it no longer shows. URLs written before the
 * list stopped showing done work spell that baseline out, and read as the
 * baseline here.
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
