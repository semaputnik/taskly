import { z } from "zod"

import type { PanelSearch } from "@/components/Records/panels"
import { STATUSES } from "./statuses"
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
  // The API's repeatable `status`: Open is its three statuses, not a keyword,
  // so the URL says exactly what the list asks for.
  status: z.array(z.enum(STATUSES)).nonempty().optional().catch(undefined),
  due_from: z.string().optional().catch(undefined),
  due_to: z.string().optional().catch(undefined),
  overdue: z.literal(true).optional().catch(undefined),
  sort: z.enum(["due_date", "priority"]).optional().catch(undefined),
  order: z.literal("desc").optional().catch(undefined),
  // The page of results being read. Like the sort, it is not a filter: it is
  // where in the results the reader is.
  page: z.number().int().min(1).optional().catch(undefined),
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
  return Object.fromEntries(FILTER_KEYS.map((key) => [key, undefined]))
}
