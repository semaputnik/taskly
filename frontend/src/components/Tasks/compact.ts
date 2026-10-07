import type { TaskPublic } from "@/client"
import { dateInWords, formatDay } from "@/lib/dates"
import { describeRecurrence } from "./recurrence"

/**
 * The words a task line puts on a task: its meta line, what it says and in
 * what order, with the due day said the way a person says it. Kept apart
 * from the row so the composition can be tested without a renderer.
 */

/**
 * How a due day reads against today: missed, today, within the coming week,
 * or further out. Only a missed day takes the alert colour; today is ink,
 * and both are set a weight up; the rest are muted.
 */
export type DueTone = "late" | "today" | "soon" | "later"

const DAY_MS = 86_400_000

/** The most days a missed due day is counted in; past it the date is said. */
const MAX_DAYS_LATE = 14

/** A `YYYY-MM-DD` day as a local midnight, never as UTC. */
function localDay(day: string): Date {
  const [year, month, date] = day.split("-").map(Number)
  return new Date(year, month - 1, date)
}

/**
 * A due day in words, measured from `today` (both `YYYY-MM-DD`): "Today",
 * "Tomorrow", a weekday within the week, "3 days late" once missed, and a
 * short date past that, with the year only when it is not this one.
 *
 * A missed day is counted in days only up to a fortnight; past that the number
 * is one nobody reads ("9775 days late"), so the date is said instead, in
 * words ("due 3 Feb 2026"), and still in the alert tone.
 * This is the one place the rule is kept: the Today page, the task list, the
 * task column and subtask lines all say a due day through here.
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

  if (done) return { text: dateInWords(due, now), tone: "later" }

  const days = Math.round((due.getTime() - now.getTime()) / DAY_MS)

  if (days < -MAX_DAYS_LATE) {
    return { text: `due ${formatDay(dueDate, now)}`, tone: "late" }
  }
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
  return { text: dateInWords(due, now), tone: "later" }
}

/** "1/3" for a task with subtasks; nothing for one without. */
export function subtaskProgress(
  task: Pick<TaskPublic, "subtask_count" | "subtasks_done">,
): string | null {
  const total = task.subtask_count ?? 0
  if (total === 0) return null
  return `${task.subtasks_done ?? 0}/${total}`
}

/**
 * Whose a task is: "you" for the owner, the bot user's name, or, for a task
 * the owner holds in Review because a bot user handed it over, that bot
 * user's name, an arrow and "you". A deleted bot user is named all the same
 * (FR-08.19). Nobody for an unassigned task.
 *
 * A bot user's id is also in `assignee_id`, so the owner is the task with an
 * assignee id and no bot user.
 */
function describeAssignee(
  task: Pick<
    Partial<TaskPublic>,
    "status" | "assignee_id" | "assignee_bot_user" | "handover"
  >,
): { text: string; handover: boolean; name?: string } | null {
  if (task.assignee_bot_user) {
    return { text: task.assignee_bot_user.name, handover: false }
  }
  if (!task.assignee_id) return null
  if (task.status === "review" && task.handover) {
    return {
      text: `${task.handover.bot_user.name} → you`,
      handover: true,
      // The name alone, so a long one can give way before the arrow does.
      name: task.handover.bot_user.name,
    }
  }
  return { text: "you", handover: false }
}

/**
 * One fact the meta line states about a task, drawn with its own glyph; the
 * due day also carries its tone.
 */
export type MetaFact =
  | { kind: "subtasks"; text: string }
  | { kind: "due"; text: string; tone: DueTone }
  | { kind: "recurrence"; text: string }
  | { kind: "tag"; text: string }
  /**
   * Whose task it is (FR-06.13). `handover` is the "bot → you" form, which
   * the line sets in a heavier grey than the other two.
   */
  | { kind: "assignee"; text: string; handover: boolean; name?: string }

/**
 * The line beneath a task's title: its facts, then the project it sits in,
 * which the row sets apart at the far right.
 */
export interface MetaLine {
  facts: MetaFact[]
  project: string | null
}

/**
 * What the line beneath a task's title says, in the order it says it: how far
 * through its subtasks it is, when it is due, how it repeats and its tags,
 * and whose it is; then its project. Whatever the task does not have is left out, so a task
 * with nothing to say has an empty meta line and its row stays one line tall.
 */
export function metaLine(
  task: Partial<
    Pick<
      TaskPublic,
      | "subtask_count"
      | "subtasks_done"
      | "due_date"
      | "recurrence"
      | "tags"
      | "status"
      | "assignee_id"
      | "assignee_bot_user"
      | "handover"
    >
  >,
  { today, projectName }: { today: string; projectName?: string },
): MetaLine {
  const facts: MetaFact[] = []
  const progress = subtaskProgress(task)
  if (progress) facts.push({ kind: "subtasks", text: progress })
  if (task.due_date) {
    const due = describeDue(task.due_date, today, {
      done: task.status === "done",
    })
    facts.push({ kind: "due", ...due })
  }
  if (task.recurrence) {
    facts.push({
      kind: "recurrence",
      text: describeRecurrence(task.recurrence),
    })
  }
  for (const tag of task.tags ?? []) facts.push({ kind: "tag", text: tag })
  const assignee = describeAssignee(task)
  if (assignee) facts.push({ kind: "assignee", ...assignee })
  return { facts, project: projectName || null }
}
