import { z } from "zod"

/**
 * The task list's view, held in the URL so it can be shared or reloaded.
 *
 * `.catch(undefined)` on every field keeps a hand-edited or stale URL from
 * breaking the page: an unusable value simply drops its filter.
 */
/**
 * The task whose detail panel is open, and whether capture is open.
 *
 * They live in the URL so the panel can be linked to and so Back closes it,
 * and they are validated by the layout rather than by each screen: the panel
 * is mounted once for the whole app, so every route carries them and a reader
 * who opens a task from the dashboard or the activity log stays where they
 * were.
 */
export const panelSearchSchema = z.object({
  task: z.string().uuid().optional().catch(undefined),
  // Capture: the panel opened on a record that does not exist yet. It is view
  // state like the open task, so it travels the same way and Back cancels it.
  capture: z.literal(true).optional().catch(undefined),
})

export const taskSearchSchema = z.object({
  project_id: z.string().optional().catch(undefined),
  // "me", "unassigned", or the id of one of the user's bot users.
  assignee: z
    .union([z.enum(["me", "unassigned"]), z.string().uuid()])
    .optional()
    .catch(undefined),
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
 * What the task list actually receives: its own filters plus the panel's view
 * state, which the layout validates for every screen.
 */
export type TaskListSearch = TaskSearch & z.infer<typeof panelSearchSchema>

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
