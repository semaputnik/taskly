import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { FolderKanban, Plus } from "lucide-react"
import { Suspense } from "react"

import { ProjectsService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { EmptyState } from "@/components/Common/EmptyState"
import PendingProjects from "@/components/Pending/PendingProjects"
import { columns } from "@/components/Projects/columns"
import { useRecordPanels } from "@/components/Records/panels"
import { Button } from "@/components/ui/button"

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

function ProjectsTableContent({
  onOpen,
  onAdd,
}: {
  onOpen: (projectId: string) => void
  onAdd: () => void
}) {
  const { data: projects } = useSuspenseQuery(getProjectsQueryOptions())

  return (
    <DataTable
      columns={columns}
      data={projects.data}
      rowLabel={(project) => `Open ${project.name}`}
      onRowClick={(project) => onOpen(project.id)}
      empty={
        <EmptyState
          icon={FolderKanban}
          title="No projects yet"
          description="A project groups tasks that belong together. Until you make one, every task lands in Inbox."
          action={<Button onClick={onAdd}>Add a project</Button>}
        />
      }
    />
  )
}

function Projects() {
  const { openProject, capture } = useRecordPanels()

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Projects</h1>
          <p className="text-muted-foreground">
            Group your tasks into projects
          </p>
        </div>
        <Button onClick={() => capture("project")}>
          <Plus />
          Add Project
        </Button>
      </div>
      <Suspense fallback={<PendingProjects />}>
        <ProjectsTableContent
          onOpen={openProject}
          onAdd={() => capture("project")}
        />
      </Suspense>
    </div>
  )
}
