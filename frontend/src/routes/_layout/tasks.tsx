import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { ProjectsService, TasksService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import PendingTasks from "@/components/Pending/PendingTasks"
import AddTask from "@/components/Tasks/AddTask"
import { getColumns } from "@/components/Tasks/columns"
import { type TaskSearch, taskSearchSchema } from "@/components/Tasks/search"
import { TaskFilters } from "@/components/Tasks/TaskFilters"
import { buildTaskTree } from "@/components/Tasks/tree"
import useAuth from "@/hooks/useAuth"

function getTasksQueryOptions(search: TaskSearch, currentUserId?: string) {
  const { assignee, ...filters } = search
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
}: {
  search: TaskSearch
  currentUserId?: string
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

  return <DataTable columns={getColumns(projectNames, depths)} data={ordered} />
}

function TasksTable({ search }: { search: TaskSearch }) {
  const { user: currentUser } = useAuth()

  // Filtering by "me" needs the id to filter on: listing before it arrives
  // would show everything, which is the opposite of what was asked for.
  if (search.assignee === "me" && !currentUser) {
    return <PendingTasks />
  }

  return (
    <Suspense fallback={<PendingTasks />}>
      <TasksTableContent search={search} currentUserId={currentUser?.id} />
    </Suspense>
  )
}

function Tasks() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Tasks</h1>
          <p className="text-muted-foreground">
            Everything you need to get done
          </p>
        </div>
        <AddTask />
      </div>
      <TaskFilters
        search={search}
        onChange={(next) =>
          navigate({ search: (previous) => ({ ...previous, ...next }) })
        }
      />
      <TasksTable search={search} />
    </div>
  )
}
