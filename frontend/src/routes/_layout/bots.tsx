import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Bot } from "lucide-react"
import { Suspense } from "react"

import AddBotUser from "@/components/Bots/AddBotUser"
import { getColumns } from "@/components/Bots/columns"
import { IssuedTokenProvider } from "@/components/Bots/IssuedToken"
import { DataTable } from "@/components/Common/DataTable"
import { EmptyState } from "@/components/Common/EmptyState"
import PendingBots from "@/components/Pending/PendingBots"
import { useRecordPanels } from "@/components/Records/panels"
import { botsQuery, scopeProjectsQuery } from "@/lib/serverState"

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

function BotsTableContent({ onOpen }: { onOpen: (botId: string) => void }) {
  const { data: bots } = useSuspenseQuery(botsQuery())
  const { data: projects } = useSuspenseQuery(scopeProjectsQuery())

  const projectsById = Object.fromEntries(
    projects.map((project) => [project.id, project]),
  )

  return (
    <DataTable
      columns={getColumns(projectsById)}
      data={bots.data}
      rowLabel={(bot) => `Open ${bot.name}`}
      onRowClick={(bot) => onOpen(bot.id)}
      empty={
        <EmptyState
          icon={Bot}
          title="No bot users yet"
          description="A bot user lets an AI agent or integration work on your tasks through the REST API — only in the projects you name, and only with the permissions you grant."
        />
      }
    />
  )
}

/**
 * Bot user management lives here and only here: creating, scoping, issuing
 * tokens for and deleting bot users takes a signed-in human, and the API refuses a bot user every one of
 * these steps (FR-07.3).
 */
function Bots() {
  const { openBot } = useRecordPanels()

  return (
    // A bot user created here is issued its token in the same step, and that
    // reveal outlives the form it came from.
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
          <BotsTableContent onOpen={openBot} />
        </Suspense>
      </div>
    </IssuedTokenProvider>
  )
}
