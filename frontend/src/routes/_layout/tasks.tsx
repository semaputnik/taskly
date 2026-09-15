import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Link as RouterLink } from "@tanstack/react-router"
import { CheckSquare, SearchX } from "lucide-react"
import { Suspense } from "react"

import { ProjectsService, TasksService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { EmptyState } from "@/components/Common/EmptyState"
import PendingTasks from "@/components/Pending/PendingTasks"
import { getColumns } from "@/components/Tasks/columns"
import {
  clearedFilters,
  hasActiveFilters,
  type TaskSearch,
  taskSearchSchema,
} from "@/components/Tasks/search"
import { TaskDetail } from "@/components/Tasks/TaskDetail"
import { TaskFilters } from "@/components/Tasks/TaskFilters"
import { buildTaskTree } from "@/components/Tasks/tree"
import { Button } from "@/components/ui/button"
import useAuth from "@/hooks/useAuth"

function getTasksQueryOptions(search: TaskSearch, currentUserId?: string) {
  // `task` names the panel that is open, not a filter. Leaving it in would put
  // it in the query key, so opening a task would refetch the list and drop the
  // whole table back to its skeleton.
  const { assignee, task: _open, ...filters } = search
  const query = {
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
    skip: 0,
    limit: 100,
  }
  return {
    queryFn: async () => (await TasksService.readTasks({ query })).data,
    queryKey: ["tasks", query],
  }
}

function getProjectsQueryOptions() {
  return {
    queryFn: async () =>
      (await ProjectsService.readProjects({ query: { skip: 0, limit: 100 } }))
        .data,
    queryKey: ["projects"],
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

function TasksTableContent({
  search,
  currentUserId,
  onClearFilters,
  onOpenTask,
}: {
  search: TaskSearch
  currentUserId?: string
  onClearFilters: () => void
  onOpenTask: (taskId: string) => void
}) {
  const { data: tasks } = useSuspenseQuery(
    getTasksQueryOptions(search, currentUserId),
  )
  const { data: projects } = useSuspenseQuery(getProjectsQueryOptions())

  const projectNames = Object.fromEntries(
    projects.data.map((project) => [project.id, project.name]),
  )
  // Nesting subtasks under their parents would reorder what the server just
  // sorted, so an explicit sort gets a flat list: the user asked for that
  // order, not for the tree.
  const { tasks: ordered, depths } = search.sort
    ? { tasks: tasks.data, depths: {} }
    : buildTaskTree(tasks.data)

  return (
    <DataTable
      columns={getColumns(projectNames, depths)}
      data={ordered}
      onRowClick={(task) => onOpenTask(task.id)}
      empty={
        hasActiveFilters(search) ? (
          <EmptyState
            icon={SearchX}
            title="No tasks match these filters"
            description="Every filter narrows the list further. Widen one, or start over."
            action={
              <Button variant="outline" onClick={onClearFilters}>
                Clear filters
              </Button>
            }
          />
        ) : (
          <EmptyState
            icon={CheckSquare}
            title="No tasks yet"
            description="Add the first one from the sidebar — or let a bot user file them for you through the REST API."
            action={
              <Button variant="outline" asChild>
                <RouterLink to="/bots">Set up a bot user</RouterLink>
              </Button>
            }
          />
        )
      }
    />
  )
}

function TasksTable({
  search,
  onClearFilters,
  onOpenTask,
}: {
  search: TaskSearch
  onClearFilters: () => void
  onOpenTask: (taskId: string) => void
}) {
  const { user: currentUser } = useAuth()

  // Filtering by "me" needs the id to filter on: listing before it arrives
  // would show everything, which is the opposite of what was asked for.
  if (search.assignee === "me" && !currentUser) {
    return <PendingTasks />
  }

  return (
    <Suspense fallback={<PendingTasks />}>
      <TasksTableContent
        search={search}
        currentUserId={currentUser?.id}
        onClearFilters={onClearFilters}
        onOpenTask={onOpenTask}
      />
    </Suspense>
  )
}

function Tasks() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const applyFilters = (next: Partial<TaskSearch>) =>
    navigate({ search: (previous) => ({ ...previous, ...next }) })
  const openTask = (task: string | undefined) =>
    navigate({ search: (previous) => ({ ...previous, task }) })

  return (
    <div className="flex flex-col gap-6">
      <TaskDetail
        taskId={search.task ?? null}
        onClose={() => openTask(undefined)}
        onOpenTask={openTask}
      />
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Tasks</h1>
        <p className="text-muted-foreground">Everything you need to get done</p>
      </div>
      <TaskFilters search={search} onChange={applyFilters} />
      <TasksTable
        search={search}
        onClearFilters={() => applyFilters(clearedFilters())}
        onOpenTask={openTask}
      />
    </div>
  )
}
