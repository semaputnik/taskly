import type { QueryClient } from "@tanstack/react-query"

import { withoutPanelState } from "@/components/Records/panels"
import {
  currentUserQuery,
  projectsQuery,
  tasksQuery,
  warmQuery,
} from "@/lib/serverState"
import { listedStatuses, type TaskListSearch } from "./search"
import { OPEN_STATUSES } from "./statuses"

/**
 * Every request the task list makes, and nothing that draws it. Kept apart
 * from the page so the route can start them as soon as it is matched, while
 * the page's own code is still on its way: the route's loader stays in the
 * first bundle, and it only reaches for this module.
 */

/** How many lines one page of the list holds. */
export const PAGE_SIZE = 25

/** One row asked for, so the request is the count and nothing else. */
const COUNT = { skip: 0, limit: 1 } as const

/**
 * The counts in the sentence under the heading: open, in Backlog, on bot
 * users and overdue, of the whole of the reader's open work.
 */
export const taskCountQueries = () => [
  tasksQuery({ status: OPEN_STATUSES, ...COUNT }),
  tasksQuery({ status: ["backlog"], ...COUNT }),
  tasksQuery({ status: OPEN_STATUSES, assigned_to_bots: true, ...COUNT }),
  tasksQuery({ status: OPEN_STATUSES, overdue: true, ...COUNT }),
]

/** What the list's filters ask the API for, before any paging. */
function filtersQuery(search: TaskListSearch, currentUserId?: string) {
  const {
    assignee,
    reporter,
    page: _page,
    ...filters
  } = withoutPanelState(search)
  return {
    ...filters,
    // A direction means something only for an order that was named: the
    // list's own order has none to reverse.
    order: search.sort ? search.order : undefined,
    // Open work, always: the list holds what is left to do, and finished
    // work is read in the activity log (ADR-0006). A chosen status narrows
    // within that rather than reaching outside it.
    status: listedStatuses(search),
    // "Me" needs the id the API filters on, a bot user is named by its own
    // id, and "unassigned" is a flag of its own.
    assignee_id:
      assignee === "me"
        ? currentUserId
        : assignee === "unassigned"
          ? undefined
          : assignee,
    unassigned: assignee === "unassigned" ? true : undefined,
    // The same shape as the assignee, minus the nobody case: a bot user is
    // named by its own id, and "me" needs the id the API filters on.
    reporter_id: reporter === "me" ? currentUserId : reporter,
  }
}

/** Whether the list has to know who the reader is before it can ask. */
export const needsReader = (search: TaskListSearch) =>
  search.assignee === "me" || search.reporter === "me"

/** The page of the list the reader is on, as the filters narrow it. */
export const taskListQuery = (search: TaskListSearch, currentUserId?: string) =>
  tasksQuery({
    ...filtersQuery(search, currentUserId),
    // The page the reader is on, asked for as such: a list that fetches a
    // window and then pages it in the browser can only page what it
    // fetched, and would report that window as the total.
    skip: ((search.page ?? 1) - 1) * PAGE_SIZE,
    limit: PAGE_SIZE,
  })

/**
 * Start the requests the task list will make, without waiting on any of
 * them: what is already cached is left alone, so a later navigation that
 * lands on the same list asks for nothing. A request that fails is the
 * page's to report, as it would be had the page asked first.
 */
export function prefetchTaskList(
  queryClient: QueryClient,
  search: TaskListSearch,
) {
  void warmQuery(queryClient, projectsQuery())
  for (const query of taskCountQueries()) void warmQuery(queryClient, query)
  if (!needsReader(search)) {
    void warmQuery(queryClient, taskListQuery(search))
    return
  }
  void warmQuery(queryClient, currentUserQuery()).then((user) => {
    if (user) void warmQuery(queryClient, taskListQuery(search, user.id))
  })
}
