import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Archive as ArchiveIcon } from "lucide-react"
import { Suspense } from "react"

import { ProjectsService, TasksService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { EmptyState } from "@/components/Common/EmptyState"
import PendingProjects from "@/components/Pending/PendingProjects"
import PendingTasks from "@/components/Pending/PendingTasks"
import { archivedColumns } from "@/components/Projects/archivedColumns"
import { getColumns } from "@/components/Tasks/columns"
import { buildTaskTree } from "@/components/Tasks/tree"

// Both keys sit under the ones the live views use, so anything that
// invalidates projects or tasks refreshes the archive as well.
function getArchivedProjectsQueryOptions() {
  const query = { archived: true, skip: 0, limit: 100 }
  return {
    queryFn: async () => (await ProjectsService.readProjects({ query })).data,
    queryKey: ["projects", query],
  }
}

function getArchivedTasksQueryOptions() {
  const query = { archived: true, skip: 0, limit: 100 }
  return {
    queryFn: async () => (await TasksService.readTasks({ query })).data,
    queryKey: ["tasks", query],
  }
}

export const Route = createFileRoute("/_layout/archive")({
  component: Archive,
  head: () => ({
    meta: [
      {
        title: "Archive - Taskly",
      },
    ],
  }),
})

function ArchivedProjectsContent() {
  const { data: projects } = useSuspenseQuery(getArchivedProjectsQueryOptions())

  return (
    <DataTable
      columns={archivedColumns}
      data={projects.data}
      empty={
        <EmptyState
          icon={ArchiveIcon}
          title="Nothing archived"
          description="Archiving a project puts it and its tasks out of the way without deleting them. They stay readable here, and can come back at any time."
        />
      }
    />
  )
}

function ArchivedTasksContent() {
  const { data: tasks } = useSuspenseQuery(getArchivedTasksQueryOptions())
  const { data: projects } = useSuspenseQuery(getArchivedProjectsQueryOptions())

  const projectNames = Object.fromEntries(
    projects.data.map((project) => [project.id, project.name]),
  )
  const { tasks: ordered, depths } = buildTaskTree(tasks.data)

  return (
    <DataTable
      columns={getColumns(projectNames, depths, { readOnly: true })}
      data={ordered}
      empty={
        <EmptyState
          icon={ArchiveIcon}
          title="No archived tasks"
          description="Tasks appear here when the project holding them is archived. They stay read-only until it is brought back."
        />
      }
    />
  )
}

/**
 * The one place archived work shows up. It is a view of its own rather than
 * a filter on the task list, so archived tasks never mix into daily views by
 * accident (FR-05.14), and nothing here can be changed until the project is
 * unarchived (FR-05.12).
 */
function Archive() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Archive</h1>
        <p className="text-muted-foreground">
          Projects set aside from daily use. They stay read-only until you
          unarchive them.
        </p>
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Projects</h2>
        <Suspense fallback={<PendingProjects />}>
          <ArchivedProjectsContent />
        </Suspense>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Tasks</h2>
        <Suspense fallback={<PendingTasks />}>
          <ArchivedTasksContent />
        </Suspense>
      </section>
    </div>
  )
}
