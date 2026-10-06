import { useQuery, useSuspenseQueries } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { BotLine, BotLinePending } from "@/components/Bots/BotLine"
import { prefetchBots, weekChangesQuery } from "@/components/Bots/queries"
import { counts } from "@/components/Bots/words"
import { textLink } from "@/components/Dashboard/shared"
import { useRecordPanels } from "@/components/Records/panels"
import { useRecordList } from "@/components/Records/walk"
import { Skeleton } from "@/components/ui/skeleton"
import {
  botsQuery,
  deletedBotsQuery,
  scopeProjectsQuery,
} from "@/lib/serverState"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/_layout/bots")({
  component: Bots,
  // The requests start as soon as the route is matched, beside the download
  // of the page's own code rather than after it. Nothing waits on them here,
  // and what is cached is left alone.
  loader: ({ context }) => {
    prefetchBots(context.queryClient)
  },
  head: () => ({
    meta: [
      {
        title: "Bots - Taskly",
      },
    ],
  }),
})

/** A section's heading: 13px, 600, over a hairline, with its count in mono. */
function Heading({ children, count }: { children: string; count: number }) {
  return (
    <h2 className="border-rule-strong flex items-baseline gap-2 border-b pb-2 text-[13px] font-semibold">
      {children}
      <span className="text-ink-3 font-mono text-xs font-normal tabular-nums">
        {count}
      </span>
    </h2>
  )
}

/**
 * The bot users as lines, and the sentence of counts above them. Every
 * request is read together, so the page is drawn once they have all come.
 */
function BotLines() {
  const [{ data: bots }, { data: deleted }, { data: scopeProjects }] =
    useSuspenseQueries({
      queries: [botsQuery(), deletedBotsQuery(), scopeProjectsQuery()],
    })
  // Whether the changes could be counted is the sentence's affair alone: a
  // log that cannot be read costs it its second half, and nothing else.
  const { data: week } = useQuery(weekChangesQuery())

  const projects = Object.fromEntries(
    scopeProjects.map((project) => [project.id, project]),
  )
  // The column walks the lines in the order they are drawn in.
  useRecordList(
    0,
    bots.data.map((bot) => bot.id),
  )
  useRecordList(
    1,
    deleted.data.map((bot) => bot.id),
  )

  if (bots.count === 0 && deleted.count === 0) {
    return (
      <div className="border-rule border-b py-8">
        <p className="font-medium">No bot users yet</p>
        <p className="text-ink-3 mt-1 max-w-prose text-pretty">
          A bot user lets an integration work on your tasks through the REST API
          — only in the projects you name, and only with the permissions you
          grant.
        </p>
      </div>
    )
  }

  const { lead, rest } = counts(bots.data, week ? week.count : null)

  return (
    <>
      <p className="text-ink-3 mb-6">
        {bots.count > 0 ? (
          <>
            <span className="text-ink font-medium">{lead}</span> {rest}
          </>
        ) : (
          "No bot users right now. Deleted ones are kept below."
        )}
      </p>

      {bots.count > 0 && (
        <section>
          <Heading count={bots.count}>Bot users</Heading>
          <ul aria-label="Bot users">
            {bots.data.map((bot) => (
              <BotLine key={bot.id} bot={bot} projects={projects} />
            ))}
          </ul>
        </section>
      )}

      {deleted.count > 0 && (
        <section className="mt-7">
          <Heading count={deleted.count}>Deleted</Heading>
          <ul aria-label="Deleted bot users">
            {deleted.data.map((bot) => (
              <BotLine key={bot.id} bot={bot} projects={projects} />
            ))}
          </ul>
        </section>
      )}
    </>
  )
}

/** The sentence and the lines while they are on their way. */
function BotLinesPending() {
  return (
    <div aria-hidden>
      <div className="mb-6 flex h-[1.45em] items-center">
        <Skeleton className="h-4 w-72 max-w-full" />
      </div>
      {Array.from({ length: 3 }).map((_, index) => (
        <BotLinePending key={index} />
      ))}
    </div>
  )
}

/**
 * Bot user management lives here and only here: creating, scoping, issuing
 * tokens for and deleting bot users takes a signed-in human, and the API
 * refuses a bot user every one of these steps (FR-07.3).
 */
function Bots() {
  const { capture } = useRecordPanels()

  return (
    <div className="max-w-[760px]">
      <div className="mb-1 flex items-baseline gap-4">
        <h1 className="text-[22px] leading-[1.2] font-semibold tracking-[-0.015em]">
          Bots
        </h1>
        <button
          type="button"
          onClick={() => capture("bot")}
          className={cn(
            textLink,
            "text-ink-2 hover:text-ink ml-auto text-[13.5px] font-medium pointer-coarse:-my-3 pointer-coarse:py-3",
          )}
        >
          <span aria-hidden>+ </span>New bot user
        </button>
      </div>
      <Suspense fallback={<BotLinesPending />}>
        <BotLines />
      </Suspense>
    </div>
  )
}
