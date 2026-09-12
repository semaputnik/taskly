import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { ProjectsService, TasksService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import PendingTasks from "@/components/Pending/PendingTasks"
import AddTask from "@/components/Tasks/AddTask"
import { getColumns } from "@/components/Tasks/columns"

function getTasksQueryOptions() {
  return {
    queryFn: async () =>
      (await TasksService.readTasks({ query: { skip: 0, limit: 100 } })).data,
    queryKey: ["tasks"],
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
  head: () => ({
    meta: [
      {
        title: "Tasks - Taskly",
      },
    ],
  }),
})

function TasksTableContent() {
  const { data: tasks } = useSuspenseQuery(getTasksQueryOptions())
  const { data: projects } = useSuspenseQuery(getProjectsQueryOptions())

  const projectNames = Object.fromEntries(
    projects.data.map((project) => [project.id, project.name]),
  )

  return <DataTable columns={getColumns(projectNames)} data={tasks.data} />
}

function TasksTable() {
  return (
    <Suspense fallback={<PendingTasks />}>
      <TasksTableContent />
    </Suspense>
  )
}

function Tasks() {
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
      <TasksTable />
    </div>
  )
}
