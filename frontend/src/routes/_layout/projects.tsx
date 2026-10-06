import { useSuspenseQueries } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { textLink } from "@/components/Dashboard/shared"
import {
  ArchivedProjectLine,
  ProjectLine,
  ProjectLinePending,
} from "@/components/Projects/ProjectLine"
import { prefetchProjects } from "@/components/Projects/queries"
import { botsIn, counts } from "@/components/Projects/words"
import { useRecordPanels } from "@/components/Records/panels"
import { useRecordList } from "@/components/Records/walk"
import { Skeleton } from "@/components/ui/skeleton"
import { botsQuery, projectsQuery } from "@/lib/serverState"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/_layout/projects")({
  component: Projects,
  // The requests start as soon as the route is matched, beside the download
  // of the page's own code rather than after it.
  loader: ({ context }) => {
    prefetchProjects(context.queryClient)
  },
  head: () => ({
    meta: [
      {
        title: "Projects - Taskly",
      },
    ],
  }),
})

/** A section's heading: 13px, 600, over a hairline, its count in mono. */
function Heading({
  children,
  count,
  note,
}: {
  children: string
  count: number
  note?: string
}) {
  return (
    <h2 className="border-rule-strong flex items-baseline gap-2 border-b pb-2 text-[13px] font-semibold">
      {children}
      <span className="text-ink-3 font-mono text-xs font-normal tabular-nums">
        {count}
      </span>
      {note && (
        <span className="text-ink-3 ml-auto text-[13px] font-normal">
          {note}
        </span>
      )}
    </h2>
  )
}

/**
 * The live projects as lines, the sentence of counts above them, and the
 * archived ones after them. Every request is read together, so the page is
 * drawn once they have all come.
 */
function ProjectLines() {
  const [{ data: live }, { data: archived }, { data: bots }] =
    useSuspenseQueries({
      queries: [
        projectsQuery(),
        projectsQuery({ archived: true }),
        botsQuery(),
      ],
    })
  // The column walks the lines in the order they are drawn in.
  useRecordList(
    0,
    live.data.map((project) => project.id),
  )
  useRecordList(
    1,
    archived.data.map((project) => project.id),
  )

  const { lead, rest } = counts(live.data)

  return (
    <>
      <p className="text-ink-3 mb-6">
        <span className="text-ink font-medium">{lead}</span> {rest}
      </p>

      <section>
        <Heading count={live.count}>Projects</Heading>
        <ul aria-label="Projects">
          {live.data.map((project) => (
            <ProjectLine
              key={project.id}
              project={project}
              bots={botsIn(project.id, bots.data)}
            />
          ))}
        </ul>
      </section>

      {archived.count > 0 && (
        <section className="mt-7">
          <Heading count={archived.count} note="Read-only until unarchived">
            Archived
          </Heading>
          <ul aria-label="Archived projects">
            {archived.data.map((project) => (
              <ArchivedProjectLine key={project.id} project={project} />
            ))}
          </ul>
        </section>
      )}
    </>
  )
}

/** The sentence and the lines while they are on their way. */
function ProjectLinesPending() {
  return (
    <div aria-hidden>
      <div className="mb-6 flex h-[1.45em] items-center">
        <Skeleton className="h-4 w-72 max-w-full" />
      </div>
      {Array.from({ length: 4 }).map((_, index) => (
        <ProjectLinePending key={index} />
      ))}
    </div>
  )
}

/**
 * Where projects are read, made, archived and deleted — and the one click
 * from a project to its tasks (FR-05.15). The archive is a section of this
 * page rather than a screen of its own (FR-05.14).
 */
function Projects() {
  const { capture } = useRecordPanels()

  return (
    <div className="page-column">
      <div className="mb-1 flex items-baseline gap-4">
        <h1 className="text-[22px] leading-[1.2] font-semibold tracking-[-0.015em]">
          Projects
        </h1>
        <button
          type="button"
          onClick={() => capture("project")}
          className={cn(
            textLink,
            "text-ink-2 hover:text-ink ml-auto text-[13.5px] font-medium pointer-coarse:-my-3 pointer-coarse:py-3",
          )}
        >
          <span aria-hidden>+ </span>New project
        </button>
      </div>
      <Suspense fallback={<ProjectLinesPending />}>
        <ProjectLines />
      </Suspense>
    </div>
  )
}
