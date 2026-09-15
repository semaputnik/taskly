import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { BotsService, ProjectsService } from "@/client"
import AddBotUser from "@/components/Bots/AddBotUser"
import { getColumns } from "@/components/Bots/columns"
import { IssuedTokenProvider } from "@/components/Bots/IssuedToken"
import { DataTable } from "@/components/Common/DataTable"
import PendingBots from "@/components/Pending/PendingBots"

function getBotsQueryOptions() {
  return {
    queryFn: async () =>
      (await BotsService.readBotUsers({ query: { skip: 0, limit: 100 } })).data,
    queryKey: ["bots"],
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

export const Route = createFileRoute("/_layout/bots")({
  component: Bots,
  head: () => ({
    meta: [
      {
        title: "Bots - Taskly",
      },
    ],
  }),
})

function BotsTableContent() {
  const { data: bots } = useSuspenseQuery(getBotsQueryOptions())
  const { data: projects } = useSuspenseQuery(getProjectsQueryOptions())

  const projectNames = Object.fromEntries(
    projects.data.map((project) => [project.id, project.name]),
  )

  return <DataTable columns={getColumns(projectNames)} data={bots.data} />
}

/**
 * Bot user management lives here and only here: creating, scoping and issuing
 * tokens takes a signed-in human, and the API refuses a bot user every one of
 * these steps (FR-07.3).
 */
function Bots() {
  return (
    <IssuedTokenProvider>
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Bots</h1>
            <p className="text-muted-foreground">
              Bot users let integrations work on your tasks through the REST API
            </p>
          </div>
          <AddBotUser />
        </div>
        <Suspense fallback={<PendingBots />}>
          <BotsTableContent />
        </Suspense>
      </div>
    </IssuedTokenProvider>
  )
}
