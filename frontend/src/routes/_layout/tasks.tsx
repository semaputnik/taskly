import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link as RouterLink } from "@tanstack/react-router"
import { useEffect } from "react"

import { PageCaptureLine } from "@/components/Dashboard/CaptureLine"
import { textLink } from "@/components/Dashboard/shared"
import { useRecordList } from "@/components/Records/walk"
import {
  CompactTaskRow,
  CompactTaskRowPending,
} from "@/components/Tasks/CompactTaskRow"
import {
  needsReader,
  PAGE_SIZE,
  prefetchTaskList,
  taskListQuery,
} from "@/components/Tasks/listQueries"
import { chooseOrder } from "@/components/Tasks/listWords"
import {
  clearedFilters,
  hasActiveFilters,
  type TaskSearch,
  taskSearchSchema,
} from "@/components/Tasks/search"
import { TaskCounts } from "@/components/Tasks/TaskCounts"
import { TaskFilters } from "@/components/Tasks/TaskFilters"
import { buildTaskTree } from "@/components/Tasks/tree"
import useAuth from "@/hooks/useAuth"
import { projectsQuery, tasksQuery } from "@/lib/serverState"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/_layout/tasks")({
  component: Tasks,
  validateSearch: taskSearchSchema,
  // The requests start as soon as the route is matched, beside the download
  // of the page's own code rather than after it. Nothing waits on them here,
  // and what is cached is left alone, so opening a task over the list or
  // walking the column asks for nothing again. The address is read as the
  // page will read it, so both ask under the same key.
  loader: ({ context, location }) => {
    const search = taskSearchSchema.safeParse(location.search)
    if (search.success) prefetchTaskList(context.queryClient, search.data)
  },
  head: () => ({
    meta: [
      {
        title: "Tasks - Taskly",
      },
    ],
  }),
})

/**
 * The task list: the product's triage surface, as one view of lines.
 *
 * The day page answers "what needs me now". This is where everything else is
 * managed — Backlog, work on bot users, a project's whole list — so it pages
 * and orders on the server, where the truth about "many" lives. It opens
 * newest filed first with each subtask under its root task; an order the
 * reader chooses puts every task at its own place instead (FR-06.4, FR-06.5).
 * A change to many tasks at once is a bot user's, through the REST API; the
 * page has no selection.
 */
function Tasks() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const { user: currentUser } = useAuth()
  const page = search.page ?? 1

  // Filtering by "me" needs the id to filter on: listing before it arrives
  // would show everything, which is the opposite of what was asked for.
  const waitingForMe = needsReader(search) && !currentUser
  const {
    data: tasks,
    isPending,
    isError,
    refetch,
  } = useQuery({
    ...taskListQuery(search, currentUser?.id),
    enabled: !waitingForMe,
  })
  const { data: projects } = useQuery(projectsQuery())

  const count = tasks?.count ?? 0
  const lastPage = Math.max(1, Math.ceil(count / PAGE_SIZE))
  const noFilters = !hasActiveFilters(search)
  // An empty list is two different things, and only the API can tell them
  // apart: no tasks at all, or nothing left open. The question is asked only
  // when the list is empty and nothing narrows it, so the ordinary case costs
  // nothing. It asks the API for done work directly — the list's own URL has
  // no way to say that any more, but the API still answers it.
  const { data: finished } = useQuery({
    ...tasksQuery({ status: ["done"], skip: 0, limit: 1 }),
    enabled: !isPending && !waitingForMe && count === 0 && noFilters,
  })

  const applyFilters = (next: Partial<TaskSearch>) =>
    // Any change to what is being shown returns to the first page: the page
    // a reader was on may not exist under the new filters.
    navigate({
      search: (previous) => ({ ...previous, ...next, page: undefined }),
    })
  const goToPage = (next: number) =>
    navigate({
      search: (previous) => ({
        ...previous,
        page: next === 1 ? undefined : next,
      }),
    })
  const sortBy = (sort: NonNullable<TaskSearch["sort"]> | undefined) =>
    navigate({
      search: (previous) => ({
        ...previous,
        ...chooseOrder(previous, sort),
        page: undefined,
      }),
    })

  // Closing the last task on the last page leaves the reader standing on a
  // page that no longer exists. Changing a filter already returns to the
  // first page; this covers the list shrinking under a reader who changed
  // nothing (ADR-0006).
  useEffect(() => {
    if (tasks && page > lastPage) goToPage(lastPage)
  })

  const projectNames = Object.fromEntries(
    (projects?.data ?? []).map((project) => [project.id, project.name]),
  )
  // Nesting subtasks under their parents would reorder what the server just
  // sorted, so a chosen order gets a flat list: the reader asked for that
  // order, not for the tree.
  const tree = tasks && !search.sort ? buildTaskTree(tasks.data) : undefined
  const rows = tasks ? (tree?.tasks ?? tasks.data) : []
  // The column walks the list in the order the lines are drawn in, so Down
  // from a task opens the line beneath it.
  useRecordList(
    0,
    rows.map((task) => task.id),
  )
  const pending = isPending || waitingForMe

  return (
    <div className="max-w-[820px]">
      <PageCaptureLine className="mb-7" />
      <h1 className="mb-1 text-[22px] leading-[1.2] font-semibold tracking-[-0.015em]">
        Tasks
      </h1>
      <TaskCounts />

      <TaskFilters search={search} onChange={applyFilters} onOrder={sortBy} />

      {pending ? (
        <div aria-hidden>
          {Array.from({
            length: Math.min(PAGE_SIZE, Math.max(count, 5)) || 5,
          }).map((_, index) => (
            <CompactTaskRowPending key={index} flush />
          ))}
        </div>
      ) : isError && !tasks ? (
        // A failed fetch is not an empty account: say so, and offer the retry.
        <div role="alert" className="border-rule border-b py-8">
          <p className="font-medium">The tasks could not be loaded</p>
          <p className="text-ink-3 mt-1">
            Nothing is lost.{" "}
            <button
              type="button"
              onClick={() => void refetch()}
              className={cn(textLink, "text-ink underline")}
            >
              Try again
            </button>
          </p>
        </div>
      ) : rows.length > 0 ? (
        // A list, so assistive technology hears how many tasks there are and
        // where each begins.
        <ul aria-label="Tasks">
          {rows.map((task) => (
            <CompactTaskRow
              key={task.id}
              task={task}
              projectName={projectNames[task.project_id]}
              depth={tree?.depths[task.id]}
              receipt
              flush
              asItem
            />
          ))}
        </ul>
      ) : (
        <Empty
          filtered={hasActiveFilters(search)}
          finished={(finished?.count ?? 0) > 0}
          onClear={() => applyFilters(clearedFilters())}
        />
      )}

      {count > 0 && (
        <div className="text-ink-3 flex items-center gap-[18px] pt-3.5 text-[13px]">
          {/* The number the server counted under these filters, not the size
              of the window that was fetched. */}
          <p aria-live="polite">
            {count === 1 ? "1 task" : `${count} tasks`}
            {count > PAGE_SIZE && ` · page ${page} of ${lastPage}`}
          </p>
          <div className="ml-auto flex gap-3.5">
            <PagerButton
              disabled={page <= 1}
              onClick={() => goToPage(page - 1)}
            >
              Previous
            </PagerButton>
            <PagerButton
              disabled={page >= lastPage}
              onClick={() => goToPage(page + 1)}
            >
              Next
            </PagerButton>
          </div>
        </div>
      )}
    </div>
  )
}

function PagerButton({
  disabled,
  onClick,
  children,
}: {
  disabled: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        textLink,
        "hover:text-ink focus-visible:text-ink disabled:pointer-events-none disabled:opacity-40 pointer-coarse:-my-3.5 pointer-coarse:px-2 pointer-coarse:py-3.5",
      )}
    >
      {children}
    </button>
  )
}

/**
 * What the page says when the list is empty, in its own words. Three cases
 * that need three different sentences: the filters excluded everything, which
 * calls for a way to undo them; everything is done, which says where the done
 * work went (ADR-0006); and nothing was ever written down, which says how to
 * begin.
 */
function Empty({
  filtered,
  finished,
  onClear,
}: {
  filtered: boolean
  finished: boolean
  onClear: () => void
}) {
  const [title, body] = filtered
    ? [
        "No tasks match these filters",
        <>
          Every filter narrows the list further. Widen one, or{" "}
          <button
            type="button"
            onClick={onClear}
            className={cn(textLink, "text-ink underline")}
          >
            clear them all
          </button>
          .
        </>,
      ]
    : finished
      ? [
          "Nothing left open",
          <>
            Everything here is done. What you finished is kept in the{" "}
            <RouterLink
              to="/activity"
              search={{ kind: "completed" as const }}
              className={cn(textLink, "text-ink underline")}
            >
              activity log
            </RouterLink>
            .
          </>,
        ]
      : [
          "No tasks yet",
          <>
            Writing one down takes a title: type it in the Add a task line. Or
            let a bot user file them for you through the REST API.{" "}
            <RouterLink
              to="/bots"
              className={cn(textLink, "text-ink underline")}
            >
              Set up a bot user
            </RouterLink>
          </>,
        ]
  return (
    <div className="border-rule border-b py-8">
      <p className="font-medium">{title}</p>
      <p className="text-ink-3 mt-1 max-w-prose text-pretty">{body}</p>
    </div>
  )
}
