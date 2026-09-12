import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { ProjectsService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import PendingProjects from "@/components/Pending/PendingProjects"
import AddProject from "@/components/Projects/AddProject"
import { columns } from "@/components/Projects/columns"

function getProjectsQueryOptions() {
  return {
    queryFn: async () =>
      (await ProjectsService.readProjects({ query: { skip: 0, limit: 100 } }))
        .data,
    queryKey: ["projects"],
  }
}

export const Route = createFileRoute("/_layout/projects")({
  component: Projects,
  head: () => ({
    meta: [
      {
        title: "Projects - Taskly",
      },
    ],
  }),
})

function ProjectsTableContent() {
  const { data: projects } = useSuspenseQuery(getProjectsQueryOptions())

  return <DataTable columns={columns} data={projects.data} />
}

function ProjectsTable() {
  return (
    <Suspense fallback={<PendingProjects />}>
      <ProjectsTableContent />
    </Suspense>
  )
}

function Projects() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Projects</h1>
          <p className="text-muted-foreground">
            Group your tasks into projects
          </p>
        </div>
        <AddProject />
      </div>
      <ProjectsTable />
    </div>
  )
}
