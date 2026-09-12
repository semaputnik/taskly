import { z } from "zod"

/**
 * The task list's view, held in the URL so it can be shared or reloaded.
 *
 * `.catch(undefined)` on every field keeps a hand-edited or stale URL from
 * breaking the page: an unusable value simply drops its filter.
 */
export const taskSearchSchema = z.object({
  project_id: z.string().optional().catch(undefined),
  assignee: z.enum(["me", "unassigned"]).optional().catch(undefined),
  tag: z.string().optional().catch(undefined),
  priority: z.enum(["P1", "P2", "P3", "P4"]).optional().catch(undefined),
  completed: z.boolean().optional().catch(undefined),
  due_from: z.string().optional().catch(undefined),
  due_to: z.string().optional().catch(undefined),
  overdue: z.literal(true).optional().catch(undefined),
  sort: z.enum(["due_date", "priority"]).optional().catch(undefined),
  order: z.literal("desc").optional().catch(undefined),
})

export type TaskSearch = z.infer<typeof taskSearchSchema>

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
  "completed",
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
