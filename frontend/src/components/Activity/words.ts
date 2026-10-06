import type { ActivityEntryPublic, ActivityKind } from "@/client"
import { dayHeading } from "@/lib/dates"

/**
 * The words on the Activity page: what the kinds are called, the sentence of
 * counts under the heading, what an empty log says for each narrowing, the
 * day groups and the pager. Plain functions, so the wording can be read and
 * tested apart from the page.
 */

/** How many lines one page of the log holds. */
export const PAGE_SIZE = 50

// The kinds of change, in the order the log offers them, and the words the
// reader picks them by. The API groups the actions behind each one; the log
// never shows a reader an action name.
export const KINDS = [
  "completed",
  "created",
  "changed",
  "deleted",
  "comments",
  "tags",
] as const satisfies readonly ActivityKind[]

export const KIND_LABELS: Record<ActivityKind, string> = {
  completed: "Completed",
  created: "Created",
  changed: "Changed",
  deleted: "Deleted & restored",
  comments: "Comments & files",
  tags: "Tags",
}

/** The log is read newest first unless the reader turns it around. */
export const ORDERS = ["newest", "oldest"] as const
export type LogOrder = (typeof ORDERS)[number]

export const ORDER_LABELS: Record<LogOrder, string> = {
  newest: "Newest first",
  oldest: "Oldest first",
}

/** Who a narrowing to the reader themselves is called in the URL. */
export const ME = "me"

function count(n: number, one: string, many: string): string {
  return n === 1 ? `1 ${one}` : `${n} ${many}`
}

/**
 * The sentence under the heading: what the log holds and how much of it is
 * the reader's bot users'. It counts the whole log, whatever it is narrowed
 * to; the pager counts what the narrowing found. `lead` is the part in full
 * ink. A count that could not be read is left out rather than guessed.
 */
export function lede(
  entries: number | null,
  byBots: number | null,
  order: LogOrder,
): { lead: string; rest: string } {
  const lead = `Every change in your account, ${order === "oldest" ? "oldest" : "newest"} first.`
  if (entries === null) return { lead, rest: "" }
  if (entries === 0) return { lead, rest: "Nothing has happened yet." }
  const total = count(entries, "entry", "entries")
  if (byBots === null) return { lead, rest: `${total}.` }
  const bots =
    byBots === 0
      ? "none of them by your bot users"
      : byBots === entries
        ? entries === 1
          ? "by one of your bot users"
          : "all by your bot users"
        : `${byBots} of them by your bot users`
  return { lead, rest: `${total}, ${bots}.` }
}

// What each kind says when it has gathered nothing. An empty narrowed log
// must never claim the account is empty: the reader narrowed it, and the
// message has to name what they narrowed it to.
const KIND_EMPTY: Record<ActivityKind, string> = {
  completed: "Nothing has been completed yet.",
  created: "Nothing has been created yet.",
  changed: "Nothing has been changed yet.",
  deleted: "Nothing has been deleted or restored yet.",
  comments: "No comments or files yet.",
  tags: "Nothing has happened to your tags yet.",
}

/** What an empty log says, in the words of what it was narrowed to. */
export function emptyMessage(
  actor: string | undefined,
  kind: ActivityKind | undefined,
): string {
  if (actor === ME) {
    return kind
      ? `You have nothing under “${KIND_LABELS[kind]}”.`
      : "You have not changed anything yet."
  }
  if (actor && kind) {
    return `This bot user has nothing under “${KIND_LABELS[kind]}”.`
  }
  if (actor) return "This bot user has not changed anything yet."
  if (kind) return KIND_EMPTY[kind]
  return "Nothing has happened in your account yet."
}

/** A day of the log: its heading, and the lines written on it. */
export interface LogDay {
  heading: string
  entries: ActivityEntryPublic[]
}

/**
 * The page's lines split by the day they were written, in the order given —
 * the heading is the one the task's history uses, so a day is named the same
 * wherever it is read. A line with no time is kept with the day before it.
 */
export function logDays(
  entries: readonly ActivityEntryPublic[],
  now: Date = new Date(),
): LogDay[] {
  const days: LogDay[] = []
  for (const entry of entries) {
    const heading = entry.created_at
      ? dayHeading(entry.created_at, now)
      : (days[days.length - 1]?.heading ?? "Today")
    const last = days[days.length - 1]
    if (last?.heading === heading) last.entries.push(entry)
    else days.push({ heading, entries: [entry] })
  }
  return days
}

/** What the pager says: how many entries these narrowings found, and where. */
export function pagerText(entries: number, page: number, last: number): string {
  const total = count(entries, "entry", "entries")
  return entries > PAGE_SIZE ? `${total} · page ${page} of ${last}` : total
}

/**
 * The pager's two buttons, back first. A page further on is older when the
 * log reads newest first and newer when it reads oldest first, so the words
 * follow the order rather than the direction.
 */
export function pagerLabels(order: LogOrder): { back: string; on: string } {
  return order === "oldest"
    ? { back: "Older", on: "Newer" }
    : { back: "Newer", on: "Older" }
}
