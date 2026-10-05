import { useSuspenseQueries } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import { ErrorBoundary } from "react-error-boundary"

import type { TaskPublic } from "@/client"
import { useRecordList } from "@/components/Records/walk"
import {
  CompactTaskRow,
  CompactTaskRowPending,
} from "@/components/Tasks/CompactTaskRow"
import { OPEN_STATUSES, type OpenStatus } from "@/components/Tasks/statuses"
import { Skeleton } from "@/components/ui/skeleton"
import { activityQuery, projectsQuery, tasksQuery } from "@/lib/serverState"
import { cn } from "@/lib/utils"
import { dayHeading, lede } from "./day"
import { changesQuery, PREVIEW_ROWS, textLink } from "./shared"
import { inAWeek, today, tomorrow } from "./when"

/**
 * The top of the day page: the date, the sentence of what needs the reader,
 * and the date bands — Overdue, Due today and the line for the rest of the
 * week. Everything here is read straight off the page, with hairlines and
 * whitespace for structure rather than frames.
 */

// The bands take every open status but Waiting, Backlog included: a due date
// counts whatever the task's status, and a waiting task's next move is
// someone else's (FR-06.11). Nor are they narrowed to the reader as
// assignee: a late task on a bot user is late all the same.
const BAND_STATUSES: OpenStatus[] = OPEN_STATUSES.filter(
  (status) => status !== "waiting",
)

type TasksQuery = Parameters<typeof tasksQuery>[0]

/** Each band, as the task list is narrowed to show the whole of it. */
const BANDS = {
  overdue: () => ({ overdue: true, status: BAND_STATUSES }),
  today: () => ({ due_from: today(), due_to: today(), status: BAND_STATUSES }),
  week: () => ({
    due_from: tomorrow(),
    due_to: inAWeek(),
    status: BAND_STATUSES,
  }),
} satisfies Record<string, () => TasksQuery>

/**
 * The bands' requests, shared with the sentence's first half through the
 * cache. The week asks for a count alone.
 */
const dayQueries = () =>
  [
    // The most pressing first: the list's own order is newest filed, which
    // is not what a band is for.
    tasksQuery({ ...BANDS.overdue(), sort: "priority", limit: PREVIEW_ROWS }),
    tasksQuery({ ...BANDS.today(), sort: "priority", limit: PREVIEW_ROWS }),
    tasksQuery({ ...BANDS.week(), limit: 1 }),
    projectsQuery(),
  ] as const

/**
 * The sentence's second half reads the activity log: the bot users' changes
 * as a count alone, and the Changes log's own request, so the sentence
 * counts what the log counts. Started by the page beside the bands.
 */
export const botChangesQuery = (since: string | null) =>
  activityQuery({ by_bots: true, since: since ?? undefined, limit: 1 })

function useDay() {
  // One hook, so the requests run side by side and the page is drawn once
  // they have all answered: a band arriving on its own would push the rest
  // of the page down after first paint.
  const [overdue, due, week, projects] = useSuspenseQueries({
    queries: dayQueries(),
  })
  return {
    overdue: overdue.data,
    due: due.data,
    weekCount: week.data.count,
    projectNames: Object.fromEntries(
      projects.data.data.map((project) => [project.id, project.name]),
    ) as Record<string, string>,
  }
}

/** How many changes the bot users made, as the second half of the sentence. */
function BotChanges({ since }: { since: string | null }) {
  const [bots, log] = useSuspenseQueries({
    queries: [botChangesQuery(since), changesQuery(since)],
  })
  return lede({
    needYou: 0,
    changes: bots.data.count,
    total: log.data.count,
    window: since ? "visit" : "ever",
  }).changes
}

/** The date: the day of the month large, the weekday, month and year beside. */
export function DayHeading() {
  const now = new Date()
  const { day, rest } = dayHeading(now)
  return (
    <h1 className="mb-1.5 leading-none">
      <time
        dateTime={today()}
        className="flex flex-wrap items-baseline gap-x-3.5 gap-y-1"
      >
        <span className="text-[56px] font-bold tracking-[-0.035em] tabular-nums">
          {day}
        </span>
        <span className="text-ink-2 text-[17px] font-medium">{rest}</span>
      </time>
    </h1>
  )
}

/** The sentence and the bands while they are on their way: the same shape. */
export function DayPending() {
  return (
    <>
      <div className="mb-8 flex h-[1.45em] items-center">
        <Skeleton className="h-4 w-80 max-w-full" />
      </div>
      {["Overdue", "Due today"].map((label) => (
        <Band key={label} label={label} count={null}>
          {Array.from({ length: 2 }).map((_, index) => (
            <CompactTaskRowPending key={index} flush />
          ))}
        </Band>
      ))}
    </>
  )
}

/**
 * One muted sentence of real counts — what needs the reader, and how many
 * changes their bot users made since the last visit — then the date bands.
 * When nothing is overdue or due, the page says so in a sentence rather than
 * drawing an empty box.
 */
export function Day({ since }: { since: string | null }) {
  const { overdue, due, weekCount, projectNames } = useDay()
  const { needs } = lede({
    needYou: overdue.count + due.count,
    changes: 0,
    total: 0,
    window: "visit",
  })
  const clear = overdue.count === 0 && due.count === 0
  // The column walks the bands in the order they are read: first.
  useRecordList(
    0,
    [...overdue.data, ...due.data].map((task) => task.id),
  )

  return (
    <>
      <p className="text-ink-3 mb-8">
        <span className="text-ink font-medium">{needs}</span>{" "}
        {/* An activity log that cannot be read costs this half of the
            sentence and the Changes log, which says so; the bands stand. */}
        <ErrorBoundary fallback={null}>
          <BotChanges since={since} />
        </ErrorBoundary>
      </p>

      {clear ? (
        <p className="text-ink-2 mb-9">
          Nothing is overdue or due today.{" "}
          {weekCount > 0 ? (
            <WeekLink count={weekCount} inline />
          ) : (
            "Nothing is due in the next seven days either."
          )}
        </p>
      ) : (
        <>
          {overdue.count > 0 && (
            <Band label="Overdue" count={overdue.count} tone="late">
              <Lines tasks={overdue.data} projectNames={projectNames} />
              {overdue.count > PREVIEW_ROWS && (
                <BandMoreLink
                  count={overdue.count - PREVIEW_ROWS}
                  search={BANDS.overdue()}
                />
              )}
            </Band>
          )}
          {due.count > 0 && (
            <Band label="Due today" count={due.count}>
              <Lines tasks={due.data} projectNames={projectNames} />
              {due.count > PREVIEW_ROWS && (
                <BandMoreLink
                  count={due.count - PREVIEW_ROWS}
                  search={BANDS.today()}
                />
              )}
            </Band>
          )}
          {weekCount > 0 && (
            <p className="-mt-5 mb-9">
              <WeekLink count={weekCount} />
            </p>
          )}
        </>
      )}
    </>
  )
}

/** A date band: a plain group under a hairline heading. */
function Band({
  label,
  count,
  tone = "default",
  children,
}: {
  label: string
  /** Null while the band is on its way. */
  count: number | null
  tone?: "default" | "late"
  children: React.ReactNode
}) {
  return (
    <section className="mb-9">
      <h2
        className={cn(
          "border-rule-strong flex items-baseline gap-2 border-b pb-2 text-[13px] font-semibold",
          tone === "late" && "text-late",
        )}
      >
        {label}
        {count !== null && (
          <span className="text-ink-3 font-mono text-xs font-normal">
            {count}
          </span>
        )}
      </h2>
      {children}
    </section>
  )
}

function Lines({
  tasks,
  projectNames,
}: {
  tasks: TaskPublic[]
  projectNames: Record<string, string>
}) {
  return tasks.map((task) => (
    <CompactTaskRow
      key={task.id}
      task={task}
      projectName={projectNames[task.project_id]}
      receipt
      flush
    />
  ))
}

/** The link that ends a band too long to show, into the task list. */
function BandMoreLink({
  count,
  search,
}: {
  count: number
  search: Record<string, unknown>
}) {
  return (
    <RouterLink
      to="/tasks"
      search={search}
      className={cn(textLink, "text-ink-3 inline-block pt-2 text-[13px]")}
    >
      {count} more <span aria-hidden>→</span>
    </RouterLink>
  )
}

/** The rest of the week, as a count that opens the list narrowed to it. */
function WeekLink({
  count,
  inline = false,
}: {
  count: number
  inline?: boolean
}) {
  const tasks = count === 1 ? "task is" : "tasks are"
  return (
    <RouterLink
      to="/tasks"
      search={BANDS.week()}
      className={cn(
        textLink,
        // Inside a sentence a link has to look like one before it is
        // hovered; on a line of its own its place says it.
        inline
          ? "text-ink decoration-rule-strong underline hover:decoration-current"
          : "text-ink-3 text-[13px]",
      )}
    >
      {inline ? (
        `${count} ${tasks} due later this week.`
      ) : (
        <>
          {count} more due later this week <span aria-hidden>→</span>
        </>
      )}
    </RouterLink>
  )
}
