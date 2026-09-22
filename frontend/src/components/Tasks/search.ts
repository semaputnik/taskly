import { z } from "zod"

import type { PanelSearch } from "@/components/Records/panels"
import { OPEN_STATUS_VALUES, OPEN_STATUSES, type OpenStatus } from "./statuses"
import { PRIORITIES } from "./writes"

/**
 * The task list's view, held in the URL so it can be shared or reloaded.
 *
 * `.catch(undefined)` on every field keeps a hand-edited or stale URL from
 * breaking the page: an unusable value simply drops its filter.
 */
export const taskSearchSchema = z.object({
  project_id: z.string().optional().catch(undefined),
  // "me", "unassigned", or the id of one of the user's bot users.
  assignee: z
    .union([z.enum(["me", "unassigned"]), z.string().uuid()])
    .optional()
    .catch(undefined),
  tag: z.string().optional().catch(undefined),
  priority: z.enum(PRIORITIES).optional().catch(undefined),
  // The API's repeatable `status`, narrowed to the open statuses: the list
  // holds open work, so Done is not a view of it to ask for (ADR-0006). A URL
  // naming Done — a bookmark from before, or a hand edit — names a status
  // this list has no way to show, and drops its filter like any other
  // unusable value, leaving the open baseline.
  status: z
    .array(z.enum(OPEN_STATUS_VALUES))
    .nonempty()
    .optional()
    .catch(undefined),
  due_from: z.string().optional().catch(undefined),
  due_to: z.string().optional().catch(undefined),
  overdue: z.literal(true).optional().catch(undefined),
  sort: z.enum(["due_date", "priority"]).optional().catch(undefined),
  order: z.literal("desc").optional().catch(undefined),
  // The page of results being read. Like the sort, it is not a filter: it is
  // where in the results the reader is.
  page: z.number().int().min(1).optional().catch(undefined),
  // How the rows are drawn: two-line compact rows, or the table, which is
  // the one named in the URL since compact is what the list opens in. Neither
  // a filter nor an order, so switching it keeps the page and the selection's
  // filters as they are.
  view: z.literal("table").optional().catch(undefined),
})

export type TaskSearch = z.infer<typeof taskSearchSchema>

/**
 * What the task list actually receives: its own filters plus the panel's view
 * state, which the layout validates for every screen.
 */
export type TaskListSearch = TaskSearch & PanelSearch

/**
 * The fields that narrow the list, as opposed to the ones that order it.
 * Clearing the filters and knowing whether any are active both read this, so
 * adding a filter to the schema is the only place that has to change.
 */
export const FILTER_KEYS = [
  "project_id",
  "assignee",
  "tag",
  "priority",
  "status",
  "due_from",
  "due_to",
  "overdue",
] as const satisfies readonly (keyof TaskSearch)[]

export function hasActiveFilters(search: TaskSearch): boolean {
  return FILTER_KEYS.some((key) => search[key] !== undefined)
}

export function clearedFilters(): Partial<TaskSearch> {
  // Clearing returns the list to what it shows without a filter, which is
  // open work — not to every status, which it has no way to show.
  return Object.fromEntries(FILTER_KEYS.map((key) => [key, undefined]))
}

/**
 * The statuses the list asks the API for: whichever open status was chosen,
 * or every open one.
 *
 * The narrowing lives here rather than in the URL, so the address stays about
 * what the reader chose. Done work is read in the activity log (ADR-0006).
 */
export function listedStatuses(
  search: Pick<TaskSearch, "status">,
): OpenStatus[] {
  return search.status ?? OPEN_STATUSES
}

/** Whether the list is in compact rows, which it opens in unless told otherwise. */
export function isCompact(search: Pick<TaskSearch, "view">): boolean {
  return search.view !== "table"
}
