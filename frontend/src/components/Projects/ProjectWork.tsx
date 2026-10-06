import { useQuery } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"

import type { ProjectPublic } from "@/client"
import { ActivityDescription } from "@/components/Activity/ActivityDescription"
import { CaptureLine } from "@/components/Dashboard/CaptureLine"
import { byDay, clock } from "@/components/Dashboard/log"
import { textLink } from "@/components/Dashboard/shared"
import { RecordSection } from "@/components/Records/RecordPanel"
import { CompactTaskRow } from "@/components/Tasks/CompactTaskRow"
import { OPEN_STATUSES } from "@/components/Tasks/statuses"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"
import { formatDateTime } from "@/lib/dates"
import { activityQuery, tasksQuery } from "@/lib/serverState"
import { cn } from "@/lib/utils"

/**
 * What a project holds and what has happened in it, read where the project is
 * read: the two sections at the foot of its column.
 *
 * Both are previews. Past a handful of lines each hands off to the surface
 * built for the long version, narrowed to this project (FR-05.15).
 */

const PREVIEW = 5

export const more = cn(
  textLink,
  "text-ink-3 hover:text-ink inline-block pt-2 text-[13px]",
)

/**
 * Its first open tasks as task lines, with a line to write another into the
 * project and the way on to the whole list.
 */
export function OpenTasks({ project }: { project: ProjectPublic }) {
  const { data, isPending, isError, refetch } = useQuery(
    tasksQuery({
      project_id: project.id,
      status: OPEN_STATUSES,
      sort: "priority",
      skip: 0,
      limit: PREVIEW,
    }),
  )
  const rest = data ? data.count - data.data.length : 0

  return (
    <RecordSection title="Open tasks" count={data?.count}>
      <div className="pt-1">
        {/* The task is filed here, whichever page is behind the column. */}
        <CaptureLine
          project={{ id: project.id, name: project.name }}
          opens="down"
        />
      </div>
      {isPending ? (
        <Pending />
      ) : isError || !data ? (
        <p role="alert" className="text-ink-2 pt-2 text-sm">
          Its tasks could not be loaded.{" "}
          <button
            type="button"
            onClick={() => void refetch()}
            className={cn(textLink, "text-ink underline")}
          >
            Try again
          </button>
        </p>
      ) : data.count === 0 ? (
        <Empty>
          No open tasks. Write one above and it lands in this project.
        </Empty>
      ) : (
        <>
          <ul aria-label={`Open tasks in ${project.name}`}>
            {data.data.map((task) => (
              <CompactTaskRow key={task.id} task={task} receipt flush asItem />
            ))}
          </ul>
          {rest > 0 && (
            <RouterLink
              to="/tasks"
              search={{ project_id: project.id }}
              className={more}
            >
              {rest} more in the list <span aria-hidden>→</span>
            </RouterLink>
          )}
        </>
      )}
    </RecordSection>
  )
}

/** What an archived project keeps: its tasks, read but not changed. */
export function KeptTasks({ project }: { project: ProjectPublic }) {
  const kept = project.task_count ?? 0
  return (
    <RecordSection title="Kept tasks" count={kept}>
      {kept === 0 ? (
        <Empty>Nothing is kept with this project.</Empty>
      ) : (
        <>
          <p className="text-ink-3 pt-2 text-sm text-pretty">
            Its tasks are out of your lists and read-only until the project is
            unarchived.
          </p>
          <RouterLink
            to="/projects/$projectId/tasks"
            params={{ projectId: project.id }}
            className={more}
          >
            Read the kept tasks <span aria-hidden>→</span>
          </RouterLink>
        </>
      )}
    </RecordSection>
  )
}

/** The latest of what happened in the project, by day, newest first. */
export function ProjectActivity({ project }: { project: ProjectPublic }) {
  const { user: currentUser } = useAuth()
  const { data, isPending, isError, refetch } = useQuery(
    activityQuery({ project_id: project.id, skip: 0, limit: PREVIEW }),
  )
  const now = new Date()

  return (
    <RecordSection title="Activity" count={data?.count}>
      {isPending ? (
        <Pending />
      ) : isError || !data ? (
        <p role="alert" className="text-ink-2 pt-2 text-sm">
          Its activity could not be loaded.{" "}
          <button
            type="button"
            onClick={() => void refetch()}
            className={cn(textLink, "text-ink underline")}
          >
            Try again
          </button>
        </p>
      ) : data.count === 0 ? (
        <Empty>
          Nothing yet. Every change to this project and the tasks in it is
          recorded here, newest first.
        </Empty>
      ) : (
        <>
          <ol aria-label={`Recent activity in ${project.name}`}>
            {byDay(data.data, now).map((day) => (
              <li key={day.entries[0].id}>
                <h4 className="text-ink-3 pt-2.5 text-[12.5px] font-normal first-letter:uppercase">
                  {day.label ?? "Today"}
                </h4>
                <ol>
                  {day.entries.map((entry) => (
                    <li
                      key={entry.id}
                      className="border-rule grid grid-cols-[4.25rem_minmax(0,1fr)] items-baseline gap-3 border-b py-2 last:border-b-0"
                    >
                      {entry.created_at ? (
                        <time
                          dateTime={entry.created_at}
                          title={formatDateTime(entry.created_at)}
                          className="text-ink-3 font-mono text-xs tabular-nums whitespace-nowrap"
                        >
                          {clock(new Date(entry.created_at))}
                        </time>
                      ) : (
                        <span />
                      )}
                      <span className="text-ink-2 text-sm break-words first-letter:lowercase">
                        <ActivityDescription
                          entry={entry}
                          currentUserId={currentUser?.id}
                        />
                      </span>
                    </li>
                  ))}
                </ol>
              </li>
            ))}
          </ol>
          <RouterLink
            to="/activity"
            search={{ project_id: project.id }}
            className={more}
          >
            Everything in this project <span aria-hidden>→</span>
          </RouterLink>
        </>
      )}
    </RecordSection>
  )
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-ink-3 pt-2 text-sm text-pretty italic">{children}</p>
  )
}

export function Pending() {
  return (
    <div className="flex flex-col gap-2 pt-3" aria-hidden>
      {Array.from({ length: 3 }).map((_, index) => (
        <Skeleton key={index} className="h-8 w-full" />
      ))}
    </div>
  )
}
