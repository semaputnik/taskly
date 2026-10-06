import type { QueryClient } from "@tanstack/react-query"

import { OPEN_STATUSES, type OpenStatus } from "@/components/Tasks/statuses"
import {
  activityQuery,
  currentUserQuery,
  projectsQuery,
  tasksQuery,
  warmQuery,
} from "@/lib/serverState"
import { LOG_LINES, PREVIEW_ROWS } from "./shared"
import { inAWeek, today, tomorrow } from "./when"
import { MY_WORK_GROUPS, MY_WORK_PREVIEW } from "./work"

/**
 * Every request the day page makes, and nothing that draws it. Kept apart
 * from the sections so the route can start them as soon as it is matched,
 * while the sections' own code is still on its way: the route's loader
 * stays in the first bundle, and it only reaches for this module.
 */

// The bands take every open status but Waiting, Backlog included: a due date
// counts whatever the task's status, and a waiting task's next move is
// someone else's (FR-06.11). Nor are they narrowed to the reader as
// assignee: a late task on a bot user is late all the same.
const BAND_STATUSES: OpenStatus[] = OPEN_STATUSES.filter(
  (status) => status !== "waiting",
)

type TasksQuery = Parameters<typeof tasksQuery>[0]

/** Each band, as the task list is narrowed to show the whole of it. */
export const BANDS = {
  overdue: () => ({ overdue: true, status: BAND_STATUSES }),
  today: () => ({ due_from: today(), due_to: today(), status: BAND_STATUSES }),
  week: () => ({
    due_from: tomorrow(),
    due_to: inAWeek(),
    status: BAND_STATUSES,
  }),
} satisfies Record<string, () => TasksQuery>

/**
 * The bands' requests, shared with the sentence's first half through the
 * cache. The week asks for a count alone.
 */
export const dayQueries = () =>
  [
    // The most pressing first: the list's own order is newest filed, which
    // is not what a band is for.
    tasksQuery({ ...BANDS.overdue(), sort: "priority", limit: PREVIEW_ROWS }),
    tasksQuery({ ...BANDS.today(), sort: "priority", limit: PREVIEW_ROWS }),
    tasksQuery({ ...BANDS.week(), limit: 1 }),
    projectsQuery(),
  ] as const

/**
 * The Changes log: the bot users' changes in the window the page counts
 * from, newest first. Its count is also what the sentence under the date
 * says, so one request serves both through the cache.
 */
export const botChangesQuery = (since: string | null) =>
  activityQuery({
    by_bots: true,
    since: since ?? undefined,
    limit: LOG_LINES,
  })

/**
 * The reader's own changes in the same window, as a count alone: the log
 * folds them into one line at its end rather than list them.
 */
export const ownChangesQuery = (since: string | null) =>
  activityQuery({ by_user: true, since: since ?? undefined, limit: 1 })

/** My work's requests, one per group, so each knows its own count. */
export const myWorkQueries = (userId: string) =>
  MY_WORK_GROUPS.map(({ status }) =>
    tasksQuery({
      assignee_id: userId,
      status: [status],
      sort: "priority",
      limit: MY_WORK_PREVIEW,
    }),
  )

/**
 * Start every request the day page will make, without waiting on any of
 * them: what is already cached is left alone, so a later navigation that
 * lands here again asks for nothing. A request that fails is the page's to
 * report, as it would be had the page asked first.
 */
export function prefetchDay(queryClient: QueryClient, since: string | null) {
  const [overdue, due, week, projects] = dayQueries()
  void warmQuery(queryClient, overdue)
  void warmQuery(queryClient, due)
  void warmQuery(queryClient, week)
  void warmQuery(queryClient, projects)
  void warmQuery(queryClient, botChangesQuery(since))
  void warmQuery(queryClient, ownChangesQuery(since))
  // My work is the reader's own, so it waits on knowing who they are.
  void warmQuery(queryClient, currentUserQuery()).then((user) => {
    if (!user) return
    for (const query of myWorkQueries(user.id))
      void warmQuery(queryClient, query)
  })
}
