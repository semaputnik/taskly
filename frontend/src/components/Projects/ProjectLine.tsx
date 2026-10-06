import { Link as RouterLink } from "@tanstack/react-router"
import { ArrowRight } from "lucide-react"

import type { ProjectPublic } from "@/client"
import { recordLink, useIsOpen } from "@/components/Records/panels"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import { keptInWords, metaFacts } from "./words"

/** The one count's link: quiet at rest, tinted under the pointer. */
const countLink =
  "focus-visible:ring-ring/50 hover:bg-rule -my-1 -mr-2 inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[13.5px] font-medium whitespace-nowrap outline-none focus-visible:ring-[3px] pointer-coarse:-my-3 pointer-coarse:py-3"

/** The neutral square that marks a project, quieter for an archived one. */
function Marker({ archived }: { archived?: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        "bg-ink-2 mt-[7px] size-2.5 rounded-[2px]",
        archived ? "opacity-25" : "opacity-55",
      )}
    />
  )
}

/**
 * A live project as a line: its marker, its name, what it is for, and beneath
 * that the facts a reader would otherwise open it to find. At the right, the
 * open count is the way into the project's tasks (FR-05.15).
 *
 * The name opens the column, as a task's title does, rather than the whole
 * line, so a list of records behaves as one.
 */
export function ProjectLine({
  project,
  bots,
}: {
  project: ProjectPublic
  /** The names of the bot users that have this project in their scope. */
  bots: string[]
}) {
  const open = useIsOpen("project", project.id)
  const facts = metaFacts(project, bots)
  const count = project.open_count ?? 0

  return (
    <li
      className={cn(
        "border-rule hover:row-tint grid grid-cols-[10px_minmax(0,1fr)_auto] items-start gap-x-3 border-b py-2.5 transition-colors last:border-b-0",
        open && "row-tint",
      )}
    >
      <Marker />
      <div className="min-w-0">
        <RouterLink
          {...recordLink("project", project.id)}
          className="focus-visible:ring-ring/50 block truncate rounded-sm leading-snug font-medium underline-offset-4 outline-none hover:underline focus-visible:ring-[3px]"
        >
          {project.name}
        </RouterLink>
        {project.description && (
          <p className="text-ink-3 mt-px line-clamp-2 text-[13.5px] leading-snug">
            {project.description}
          </p>
        )}
        {facts.length > 0 && (
          <ul className="text-ink-3 mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[0.8125rem] leading-tight">
            {facts.map((fact) => (
              <li
                key={fact.text}
                className={cn(fact.late && "text-late font-medium")}
              >
                {fact.text}
              </li>
            ))}
          </ul>
        )}
      </div>
      {count > 0 ? (
        <RouterLink
          to="/tasks"
          search={{ project_id: project.id }}
          aria-label={`${count} open, open the list of ${project.name}`}
          className={countLink}
        >
          {count} open
          <ArrowRight aria-hidden className="size-3" strokeWidth={1.5} />
        </RouterLink>
      ) : (
        <span className="text-ink-3 text-[13.5px] whitespace-nowrap">
          No open tasks
        </span>
      )}
    </li>
  )
}

/**
 * An archived project as a quiet line: still named, still opening its column
 * (where it is unarchived), with its kept tasks one click away, read-only.
 */
export function ArchivedProjectLine({ project }: { project: ProjectPublic }) {
  const open = useIsOpen("project", project.id)
  const kept = project.task_count ?? 0

  return (
    <li
      className={cn(
        "border-rule hover:row-tint grid grid-cols-[10px_minmax(0,1fr)_auto] items-start gap-x-3 border-b py-2.5 transition-colors last:border-b-0",
        open && "row-tint",
      )}
    >
      <Marker archived />
      <div className="min-w-0">
        <RouterLink
          {...recordLink("project", project.id)}
          className="text-ink-3 focus-visible:ring-ring/50 block truncate rounded-sm leading-snug font-medium underline-offset-4 outline-none hover:underline focus-visible:ring-[3px]"
        >
          {project.name}
        </RouterLink>
        <p className="text-ink-3 mt-1 text-[0.8125rem] leading-tight">
          {kept === 0
            ? "No tasks kept with it"
            : `${keptInWords(project)} kept with it`}
        </p>
      </div>
      {kept > 0 && (
        <RouterLink
          to="/projects/$projectId/tasks"
          params={{ projectId: project.id }}
          aria-label={`${keptInWords(project)}, read the kept tasks of ${project.name}`}
          className={cn(countLink, "text-ink-3 hover:text-ink")}
        >
          {keptInWords(project)}
          <ArrowRight aria-hidden className="size-3" strokeWidth={1.5} />
        </RouterLink>
      )}
    </li>
  )
}

/** A line while its project is on its way. */
export function ProjectLinePending() {
  return (
    <div className="border-rule grid grid-cols-[10px_minmax(0,1fr)_auto] gap-x-3 border-b py-2.5 last:border-b-0">
      <Skeleton className="mt-[7px] size-2.5 rounded-[2px]" />
      <div className="flex flex-col gap-1.5">
        <Skeleton className="h-4 w-36" />
        <Skeleton className="h-3 w-56 max-w-full" />
      </div>
      <Skeleton className="h-3 w-16" />
    </div>
  )
}
