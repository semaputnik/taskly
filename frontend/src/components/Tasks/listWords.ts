import { formatDay } from "@/lib/dates"
import { NATURAL_ORDER, type TaskSearch } from "./search"

/**
 * The words on the task list's own controls, as plain functions so the
 * wording for zero, one and many, and for each direction an order can run,
 * can be read and tested apart from the page.
 */

export interface ListCounts {
  open: number
  backlog: number
  onBots: number
  overdue: number
}

/**
 * The sentence under the heading: what is open, in ink, then what is true of
 * it — in Backlog, on bot users, overdue — in the muted voice. A figure of
 * none is left out rather than said, so the sentence is only ever news.
 */
export function counts({ open, backlog, onBots, overdue }: ListCounts): {
  lead: string
  rest: string
} {
  if (open === 0) return { lead: "Nothing is open.", rest: "" }
  const parts = [
    backlog > 0 && `${backlog} in Backlog`,
    onBots > 0 && (onBots === 1 ? "1 on a bot user" : `${onBots} on bot users`),
    overdue > 0 && `${overdue} overdue`,
  ].filter(Boolean)
  return {
    lead: `${open} open.`,
    rest: parts.length > 0 ? `${parts.join(", ")}.` : "",
  }
}

type Sort = NonNullable<TaskSearch["sort"]>

/** Each order's name for the direction it runs in, natural first. */
const ORDER_WORDS: Record<Sort, { asc: string; desc: string }> = {
  due_date: { asc: "Due soonest first", desc: "Due latest first" },
  priority: { asc: "Priority, P1 first", desc: "Priority, P4 first" },
  created_at: { asc: "Filed, oldest first", desc: "Filed, newest first" },
}

/**
 * What the order menu's button says, and whether the order is running
 * against its natural direction. No sort in the URL is the list's own order:
 * newest first, with each subtask under its root task.
 */
export function orderChoice(search: Pick<TaskSearch, "sort" | "order">): {
  label: string
  reversed: boolean
} {
  if (!search.sort) return { label: "Newest first", reversed: false }
  const natural = NATURAL_ORDER[search.sort]
  const direction = search.order ?? natural
  return {
    label: ORDER_WORDS[search.sort][direction],
    reversed: direction !== natural,
  }
}

/**
 * What the URL says after an order is chosen. Choosing an order gives it the
 * direction it naturally runs in; choosing it again reverses it, so direction
 * costs no control of its own (FR-06.4). Only a reversal is written down.
 * Choosing the list's own order — newest first, with subtasks under their
 * roots — clears both.
 */
export function chooseOrder(
  current: Pick<TaskSearch, "sort" | "order">,
  chosen: Sort | undefined,
): Pick<TaskSearch, "sort" | "order"> {
  if (!chosen) return { sort: undefined, order: undefined }
  const natural = NATURAL_ORDER[chosen]
  const reversing =
    current.sort === chosen && (current.order ?? natural) === natural
  return {
    sort: chosen,
    order: reversing ? (natural === "asc" ? "desc" : "asc") : undefined,
  }
}

/**
 * What the time filter's button says when it is set: overdue, a range, or
 * one open end of one. Nothing when it narrows nothing.
 */
export function timeLabel(
  search: Pick<TaskSearch, "overdue" | "due_from" | "due_to">,
): string | undefined {
  const { overdue, due_from: from, due_to: to } = search
  const range =
    from && to
      ? `${formatDay(from)} – ${formatDay(to)}`
      : from
        ? `From ${formatDay(from)}`
        : to
          ? `To ${formatDay(to)}`
          : undefined
  if (overdue && range) {
    // "Overdue, to 09.10.2026": the range's own words, lower-cased to read on.
    return `Overdue, ${range.charAt(0).toLowerCase()}${range.slice(1)}`
  }
  return overdue ? "Overdue" : range
}
