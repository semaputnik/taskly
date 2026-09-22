import type { TaskPublic } from "@/client"

/**
 * The words a compact task row puts on a task: its due day said the way a
 * person says it, and how far through its subtasks it is. Kept apart from the
 * row so the wording can be tested without a renderer.
 */

/**
 * How a due day reads against today: missed, today, within the coming week,
 * or further out. Only a missed day takes the alert colour; today is ink,
 * and the rest are muted.
 */
export type DueTone = "late" | "today" | "soon" | "later"

const DAY_MS = 86_400_000

/** A `YYYY-MM-DD` day as a local midnight, never as UTC. */
function localDay(day: string): Date {
  const [year, month, date] = day.split("-").map(Number)
  return new Date(year, month - 1, date)
}

/** A day written out plainly, carrying the year only when it is not this one. */
function plainDay(due: Date, now: Date): string {
  return due.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    ...(due.getFullYear() !== now.getFullYear() && { year: "numeric" }),
  })
}

/**
 * A due day in words, measured from `today` (both `YYYY-MM-DD`): "Today",
 * "Tomorrow", a weekday within the week, "3 days late" once missed, and a
 * short date past that, with the year only when it is not this one.
 *
 * A done task's due day is read plainly instead, at every distance. The
 * relative wording and the alert tone both say the same thing — this is still
 * owed — and neither is true of work that is finished. Said of a done task,
 * "3 days late" is also a number that grows for as long as the task is kept.
 */
export function describeDue(
  dueDate: string,
  today: string,
  { done = false }: { done?: boolean } = {},
): { text: string; tone: DueTone } {
  const due = localDay(dueDate)
  const now = localDay(today)

  if (done) return { text: plainDay(due, now), tone: "later" }

  const days = Math.round((due.getTime() - now.getTime()) / DAY_MS)

  if (days < -1) return { text: `${-days} days late`, tone: "late" }
  if (days === -1) return { text: "Yesterday", tone: "late" }
  if (days === 0) return { text: "Today", tone: "today" }
  if (days === 1) return { text: "Tomorrow", tone: "soon" }
  if (days < 7) {
    return {
      text: due.toLocaleDateString(undefined, { weekday: "long" }),
      tone: "soon",
    }
  }
  return { text: plainDay(due, now), tone: "later" }
}

/** "1/3" for a task with subtasks; nothing for one without. */
export function subtaskProgress(
  task: Pick<TaskPublic, "subtask_count" | "subtasks_done">,
): string | null {
  const total = task.subtask_count ?? 0
  if (total === 0) return null
  return `${task.subtasks_done ?? 0}/${total}`
}
