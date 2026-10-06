import { useQuery } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"

import type { BotUserPublic } from "@/client"
import { ActivityDescription } from "@/components/Activity/ActivityDescription"
import { byDay, clock } from "@/components/Dashboard/log"
import { textLink } from "@/components/Dashboard/shared"
import { RecordSection } from "@/components/Records/RecordPanel"
import { CompactTaskRow } from "@/components/Tasks/CompactTaskRow"
import { OPEN_STATUSES } from "@/components/Tasks/statuses"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"
import { formatDateTime } from "@/lib/dates"
import {
  activityQuery,
  scopeProjectsQuery,
  tasksQuery,
} from "@/lib/serverState"
import { cn } from "@/lib/utils"

/**
 * What a bot user is doing and what it has done, read where the bot user is
 * read: the two sections at the foot of its column.
 *
 * The product's distinctive fact is that a person and their bot users work the
 * same records, and the log has always known which one did what — but the
 * only way to ask was to scroll the whole account's history. Both are
 * previews: past a handful of lines each hands off to the surface built for
 * the long version, narrowed to this bot user.
 */

const PREVIEW = 5

const more = cn(
  textLink,
  "text-ink-3 hover:text-ink inline-block pt-2 text-[13px]",
)

/** Its open tasks, whatever stage that work is at, as task lines. */
export function OnItsPlate({ bot }: { bot: BotUserPublic }) {
  const { data, isPending, isError, refetch } = useQuery(
    tasksQuery({
      assignee_id: bot.id,
      status: OPEN_STATUSES,
      sort: "priority",
      skip: 0,
      limit: PREVIEW,
    }),
  )
  const { data: projects } = useQuery(scopeProjectsQuery())
  const names = Object.fromEntries(
    (projects ?? []).map((project) => [project.id, project.name]),
  )

  return (
    <RecordSection title="On its plate" count={data?.count}>
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
          No open tasks are assigned to this bot user.
          {!bot.deleted &&
            " Assign one from a task's panel to make it responsible for it."}
        </Empty>
      ) : (
        <>
          <ul aria-label={`Tasks assigned to ${bot.name}`}>
            {data.data.map((task) => (
              <CompactTaskRow
                key={task.id}
                task={task}
                projectName={names[task.project_id]}
                receipt
                flush
                asItem
              />
            ))}
          </ul>
          <RouterLink
            to="/tasks"
            search={{ assignee: bot.id, status: OPEN_STATUSES }}
            className={more}
          >
            All its tasks <span aria-hidden>→</span>
          </RouterLink>
        </>
      )}
    </RecordSection>
  )
}

/** The latest of what it did, by day, newest first. */
export function BotActivity({ bot }: { bot: BotUserPublic }) {
  const { user: currentUser } = useAuth()
  const { data, isPending, isError, refetch } = useQuery(
    activityQuery({ actor_bot_user_id: bot.id, skip: 0, limit: PREVIEW }),
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
          Nothing yet. Every change this bot user makes — a task created, a
          comment added, a tag applied — is recorded here, newest first.
        </Empty>
      ) : (
        <>
          <ol aria-label={`Recent activity by ${bot.name}`}>
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
            search={{ actor: bot.id }}
            className={more}
          >
            Everything it did <span aria-hidden>→</span>
          </RouterLink>
        </>
      )}
    </RecordSection>
  )
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-ink-3 pt-2 text-sm text-pretty italic">{children}</p>
  )
}

function Pending() {
  return (
    <div className="flex flex-col gap-2 pt-3" aria-hidden>
      {Array.from({ length: 3 }).map((_, index) => (
        <Skeleton key={index} className="h-8 w-full" />
      ))}
    </div>
  )
}
