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

/** Everything that is not done: what "Open" means wherever it is offered. */
export const OPEN_STATUSES: TaskStatus[] = ["todo", "in_progress", "waiting"]

export const STATUS_LABELS: Record<TaskStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  waiting: "Waiting",
  done: "Done",
}

/**
 * The status filter as the list reads it: nothing, Open, or one status.
 * Anything else a hand-edited URL holds is shown as the statuses it names.
 */
export function describeStatusFilter(
  statuses: readonly TaskStatus[] | undefined,
): string | undefined {
  if (!statuses?.length) return undefined
  if (isOpenFilter(statuses)) return "Open"
  return statuses.map((status) => STATUS_LABELS[status]).join(", ")
}

export function isOpenFilter(statuses: readonly TaskStatus[]): boolean {
  return (
    statuses.length === OPEN_STATUSES.length &&
    OPEN_STATUSES.every((status) => statuses.includes(status))
  )
}
