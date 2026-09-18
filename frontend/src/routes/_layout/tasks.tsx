import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link as RouterLink } from "@tanstack/react-router"
import { CheckSquare, SearchX } from "lucide-react"
import { useRef, useState } from "react"

import { type TaskPublic, TasksService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { EmptyState } from "@/components/Common/EmptyState"
import { useRecordPanels, withoutPanelState } from "@/components/Records/panels"
import {
  CompactTaskRow,
  CompactTaskRowPending,
} from "@/components/Tasks/CompactTaskRow"
import { getColumns } from "@/components/Tasks/columns"
import {
  clearedFilters,
  FILTER_KEYS,
  hasActiveFilters,
  type TaskListSearch,
  type TaskSearch,
  taskSearchSchema,
} from "@/components/Tasks/search"
import { TaskBulkActions } from "@/components/Tasks/TaskBulkActions"
import { TaskFilters } from "@/components/Tasks/TaskFilters"
import { buildTaskTree } from "@/components/Tasks/tree"
import { Button } from "@/components/ui/button"
import useAuth from "@/hooks/useAuth"
import { projectsQuery, tasksQuery } from "@/lib/serverState"
import { toastError } from "@/lib/toasts"

const PAGE_SIZE = 25

// What one batch can carry, matching the API's own limit on a batch's ids.
const MAX_BATCH = 500

// One empty set, so a cleared selection is the same value every render.
const EMPTY: ReadonlySet<string> = new Set()

// Which column sorts by what. Only these two order the list; the rest are
// read, not scanned in order.
const SORT_FIELDS = { due_date: "due_date", priority: "priority" }

/** What the list's filters ask the API for, before any paging. */
function filtersQuery(search: TaskListSearch, currentUserId?: string) {
  const {
    assignee,
    page: _page,
    view: _view,
    ...filters
  } = withoutPanelState(search)
  return {
    ...filters,
    // "Me" needs the id the API filters on, a bot user is named by its own
    // id, and "unassigned" is a flag of its own.
    assignee_id:
      assignee === "me"
        ? currentUserId
        : assignee === "unassigned"
          ? undefined
          : assignee,
    unassigned: assignee === "unassigned" ? true : undefined,
  }
}

export const Route = createFileRoute("/_layout/tasks")({
  component: Tasks,
  validateSearch: taskSearchSchema,
  head: () => ({
    meta: [
      {
        title: "Tasks - Taskly",
      },
    ],
  }),
})

/**
 * The task list: the product's triage surface.
 *
 * The dashboard answers "what needs me now". This answers the question only a
 * table can — working through many tasks at once — so it pages and sorts on
 * the server, where the truth about "many" lives, and its rows can be selected
 * and acted on as a batch.
 */
function Tasks() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const { openTask, capture } = useRecordPanels()
  const { user: currentUser } = useAuth()
  const page = search.page ?? 1

  // Which tasks are selected, gathered across pages of one filter set. A
  // selection outlives paging, because a batch is often collected page by
  // page — and it is dropped the moment the filters change, because nobody
  // should act on tasks they can no longer see (stories 16, 17). The filters
  // it belongs to are held with it, and compared while rendering, so there is
  // no window in which the bar offers to act on tasks that are gone.
  const filterKey = JSON.stringify(FILTER_KEYS.map((key) => search[key]))
  const [selection, setSelection] = useState({
    filters: filterKey,
    ids: new Set<string>(),
  })
  const selected = selection.filters === filterKey ? selection.ids : EMPTY
  const setSelected = (next: (ids: Set<string>) => Set<string>) =>
    setSelection((previous) => ({
      filters: filterKey,
      ids: next(previous.filters === filterKey ? previous.ids : new Set()),
    }))
  const clearSelection = () =>
    setSelection({ filters: filterKey, ids: new Set() })

  // Filtering by "me" needs the id to filter on: listing before it arrives
  // would show everything, which is the opposite of what was asked for.
  const waitingForMe = search.assignee === "me" && !currentUser
  const filters = filtersQuery(search, currentUser?.id)
  const { data: tasks, isPending } = useQuery({
    ...tasksQuery({
      ...filters,
      // The page the reader is on, asked for as such: a table that fetches a
      // window and then pages it in the browser can only page what it
      // fetched, and would report that window as the total.
      skip: (page - 1) * PAGE_SIZE,
      limit: PAGE_SIZE,
    }),
    enabled: !waitingForMe,
  })
  const { data: projects } = useQuery(projectsQuery())

  const applyFilters = (next: Partial<TaskSearch>) =>
    // Any change to what is being shown returns to the first page: the page
    // a reader was on may not exist under the new filters (story 10).
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
  // The view is how the rows are drawn, so it keeps the page the reader is on.
  const setView = (view: TaskSearch["view"]) =>
    navigate({ search: (previous) => ({ ...previous, view }) })
  const sortBy = (field: string) =>
    navigate({
      search: (previous) => ({
        ...previous,
        sort: field as TaskSearch["sort"],
        // The same header again reverses it: direction costs no control of
        // its own (story 6).
        order:
          previous.sort === field && previous.order !== "desc"
            ? ("desc" as const)
            : undefined,
        page: undefined,
      }),
    })

  // Every task this list has shown, so a batch can be checked against what
  // the selected tasks are before it is sent — a selection outlives pages.
  const seen = useRef(new Map<string, TaskPublic>())
  for (const task of tasks?.data ?? []) seen.current.set(task.id, task)

  const count = tasks?.count ?? 0
  const lastPage = Math.max(1, Math.ceil(count / PAGE_SIZE))
  const projectNames = Object.fromEntries(
    (projects?.data ?? []).map((project) => [project.id, project.name]),
  )
  // Nesting subtasks under their parents would reorder what the server just
  // sorted, so an explicit sort gets a flat list: the reader asked for that
  // order, not for the tree.
  const rows: TaskPublic[] = tasks
    ? search.sort
      ? tasks.data
      : buildTaskTree(tasks.data).tasks
    : []
  const depths = tasks && !search.sort ? buildTaskTree(tasks.data).depths : {}

  const empty = hasActiveFilters(search) ? (
    <EmptyState
      icon={SearchX}
      title="No tasks match these filters"
      description="Every filter narrows the list further. Widen one, or start over."
      action={
        <Button
          variant="outline"
          onClick={() => applyFilters(clearedFilters())}
        >
          Clear filters
        </Button>
      }
    />
  ) : (
    <EmptyState
      icon={CheckSquare}
      title="No tasks yet"
      description="Writing one down takes a title — or let a bot user file them for you through the REST API."
      action={
        <div className="flex flex-wrap items-center justify-center gap-2">
          <Button onClick={() => capture("task")}>Add a task</Button>
          <Button variant="outline" asChild>
            <RouterLink to="/bots">Set up a bot user</RouterLink>
          </Button>
        </div>
      }
    />
  )

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Tasks</h1>
        <p className="text-muted-foreground">Everything you need to get done</p>
      </div>

      <TaskFilters
        search={search}
        onChange={applyFilters}
        onViewChange={setView}
      />

      {/* Choosing many is the table's job: compact rows cannot show what is
          selected, so the bar waits until the table is back. */}
      {selected.size > 0 && search.view !== "compact" && (
        <TaskBulkActions
          selected={[...selected]}
          known={[...selected].flatMap((id) => seen.current.get(id) ?? [])}
          projects={projects?.data ?? []}
          onDone={clearSelection}
          onClear={clearSelection}
          // "Everything on this page" and "everything that matches" are
          // different acts, so the bar says which one is in force and offers
          // the other rather than guessing (story 13).
          matching={count}
          pageIsWhollySelected={
            rows.length > 0 && rows.every((task) => selected.has(task.id))
          }
          onSelectAllMatching={async () => {
            try {
              const all = await TasksService.readTasks({
                query: { ...filters, skip: 0, limit: MAX_BATCH },
              })
              const matched = all.data?.data ?? []
              for (const task of matched) seen.current.set(task.id, task)
              setSelected(() => new Set(matched.map((task) => task.id)))
            } catch (error) {
              toastError(error)
            }
          }}
        />
      )}

      {search.view === "compact" ? (
        <CompactList
          tasks={rows}
          projectNames={projectNames}
          pending={isPending || waitingForMe}
          pendingRows={Math.min(PAGE_SIZE, Math.max(count, 5)) || 5}
          empty={empty}
        />
      ) : (
        <DataTable
          scrollLabel="Tasks, scrollable sideways"
          columns={getColumns(projectNames, depths)}
          data={rows}
          pending={isPending || waitingForMe}
          pendingRows={Math.min(PAGE_SIZE, Math.max(count, 5)) || 5}
          rowLabel={(task) => `Open ${task.title}`}
          onRowClick={(task) => openTask(task.id)}
          selection={{
            ids: selected,
            idOf: (task) => task.id,
            label: (task) => `Select ${task.title}`,
            onToggle: (id, isSelected) =>
              setSelected((previous) => {
                const next = new Set(previous)
                if (isSelected) next.add(id)
                else next.delete(id)
                return next
              }),
            onTogglePage: (ids, isSelected) =>
              setSelected((previous) => {
                const next = new Set(previous)
                for (const id of ids) {
                  if (isSelected) next.add(id)
                  else next.delete(id)
                }
                return next
              }),
          }}
          sorting={{
            fields: SORT_FIELDS,
            field: search.sort,
            descending: search.order === "desc",
            onSort: sortBy,
          }}
          empty={empty}
        />
      )}

      {count > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* The number the server counted under these filters, not the size
              of the window that was fetched (story 1). */}
          <p aria-live="polite" className="text-muted-foreground text-sm">
            {count === 1 ? "1 task" : `${count} tasks`}
            {count > PAGE_SIZE && ` · page ${page} of ${lastPage}`}
          </p>
          {count > PAGE_SIZE && (
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => goToPage(page - 1)}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= lastPage}
                onClick={() => goToPage(page + 1)}
              >
                Next
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * The list as compact rows: the same page, filters and order as the table,
 * in the row the dashboard uses. It reads and closes tasks; choosing many at
 * once is the table's job, so it has no selection of its own.
 */
function CompactList({
  tasks,
  projectNames,
  pending,
  pendingRows,
  empty,
}: {
  tasks: TaskPublic[]
  projectNames: Record<string, string>
  pending: boolean
  pendingRows: number
  empty: React.ReactNode
}) {
  return (
    <div className="bg-card overflow-hidden rounded-lg border">
      {pending
        ? Array.from({ length: pendingRows }).map((_, index) => (
            <CompactTaskRowPending key={index} />
          ))
        : tasks.length > 0
          ? tasks.map((task) => (
              <CompactTaskRow
                key={task.id}
                task={task}
                projectName={projectNames[task.project_id]}
              />
            ))
          : empty}
    </div>
  )
}
