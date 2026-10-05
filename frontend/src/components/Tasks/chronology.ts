import type { ActivityEntryPublic, CommentPublic } from "@/client"
import { dayHeading } from "@/lib/dates"
import { describeTaskEvent } from "./taskEvents"

/** One line of a task's history: something that happened, or something said. */
export type Moment =
  | {
      kind: "event"
      id: string
      at: string
      entry: ActivityEntryPublic
      text: string
    }
  | { kind: "comment"; id: string; at: string; comment: CommentPublic }

/** A day of the history and what happened in it, oldest first. */
export interface Day {
  heading: string
  moments: Moment[]
}

/**
 * A task's log entries and its comments as one history, oldest first.
 *
 * The log arrives newest first, as the log is read everywhere; the panel
 * reads down from the start. A comment is in the log too, as the entry that
 * says it was written, edited or deleted, but it is shown as the comment
 * itself, so those entries have no line of their own (`describeTaskEvent`
 * leaves them out) and nothing is told twice.
 */
export function chronology(
  entries: readonly ActivityEntryPublic[],
  comments: readonly CommentPublic[],
  now: Date = new Date(),
): Day[] {
  const moments: Moment[] = []
  for (const entry of [...entries].reverse()) {
    const text = describeTaskEvent(entry)
    if (text && entry.created_at) {
      moments.push({
        kind: "event",
        id: entry.id,
        at: entry.created_at,
        entry,
        text,
      })
    }
  }
  for (const comment of comments) {
    if (comment.created_at) {
      moments.push({
        kind: "comment",
        id: comment.id,
        at: comment.created_at,
        comment,
      })
    }
  }
  // Array.prototype.sort is stable: moments of the same instant keep the
  // order the log and the thread gave them.
  moments.sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime())

  const days: Day[] = []
  for (const moment of moments) {
    const heading = dayHeading(moment.at, now)
    const last = days[days.length - 1]
    if (last?.heading === heading) last.moments.push(moment)
    else days.push({ heading, moments: [moment] })
  }
  return days
}
