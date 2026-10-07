import type { TaskHandover } from "@/client"
import type { OpenStatus } from "@/components/Tasks/statuses"
import { STATUS_LABELS } from "@/components/Tasks/statuses"
import { dateInWords } from "@/lib/dates"

/**
 * My work's words and narrowing (FR-06.7): which groups it draws and in what
 * order, how each opens the task list, and the hand-over line under a task a
 * bot user moved to Review. Plain functions, so they read and test apart
 * from the page.
 */

/** How many lines a group shows before it hands off to the task list. */
export const MY_WORK_PREVIEW = 3

/**
 * The groups, in the order work moves: what is under way, what came back to
 * be checked, what is decided on, and what waits on someone else. Backlog is
 * not one of them: it is not yet work in hand.
 */
export const MY_WORK_GROUPS = (
  ["in_progress", "review", "todo", "waiting"] as const satisfies OpenStatus[]
).map((status) => ({ status, label: STATUS_LABELS[status] }))

export type MyWorkStatus = (typeof MY_WORK_GROUPS)[number]["status"]

/** The task list narrowed as a group is: its status, on the reader, P1 first. */
export function myWorkSearch(status: MyWorkStatus) {
  return {
    status: [status] as [MyWorkStatus],
    assignee: "me" as const,
    sort: "priority" as const,
  }
}

const DAY_MS = 86_400_000

function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
}

/** When, as a person says it of something finished: today's time, or the day. */
function finishedWhen(at: Date, now: Date, locale?: string): string {
  const time = at.toLocaleTimeString(locale, {
    hour: "2-digit",
    minute: "2-digit",
  })
  const days = Math.round((startOfDay(now) - startOfDay(at)) / DAY_MS)
  if (days <= 0) return `at ${time}`
  if (days === 1) return `yesterday at ${time}`
  if (days < 7) {
    return `on ${at.toLocaleDateString(locale, { weekday: "long" })}`
  }
  return `on ${dateInWords(at, now, locale)}`
}

/**
 * The line under a task a bot user handed over: who, set apart so the page
 * can weight it, and the rest of the sentence. A deleted bot user is still
 * named, as it was called, and said to be gone.
 */
export function handoverLine(
  handover: TaskHandover,
  now: Date,
  locale?: string,
): { who: string; rest: string } {
  const { name, deleted } = handover.bot_user
  return {
    who: deleted ? `${name} (deleted)` : name,
    rest: `finished this ${finishedWhen(new Date(handover.at), now, locale)} and handed it to you`,
  }
}
