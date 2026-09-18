import { useSuspenseQueries } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import { ArrowRight, CheckCheck } from "lucide-react"

import type { TaskStatus } from "@/client"
import {
  CompactTaskRow,
  CompactTaskRowPending,
} from "@/components/Tasks/CompactTaskRow"
import { projectsQuery, tasksQuery } from "@/lib/serverState"
import { Group, MoreLink, PREVIEW_ROWS } from "./sheet"
import { inAWeek, today, tomorrow } from "./when"

// The work the owner can move themselves. A waiting task is open too, but its
// next move is someone else's, so it has a band of its own rather than
// nagging from Overdue and Today.
const ACTIONABLE: TaskStatus[] = ["todo", "in_progress"]
const WAITING: TaskStatus[] = ["waiting"]

type TasksQuery = Parameters<typeof tasksQuery>[0]

const tasksIn = (status: TaskStatus[], query: TasksQuery) =>
  tasksQuery({ ...query, status })

const actionable = (query: TasksQuery) => tasksIn(ACTIONABLE, query)

/** The sheet while its bands are on their way. */
export function NeedsYouPending() {
  return (
    <div className="bg-card overflow-hidden rounded-lg border">
      {["Overdue", "Due today"].map((label) => (
        <Group key={label} label={label} count={0}>
          {Array.from({ length: 2 }).map((_, index) => (
            <CompactTaskRowPending key={index} />
          ))}
        </Group>
      ))}
    </div>
  )
}

/**
 * The work the day is actually asking for: what is late, what is due today,
 * and how much is waiting behind them. It is a preview, not the task list —
 * anything longer than a few rows hands off to Tasks.
 */
export function NeedsYou() {
  // One hook, so the five requests run side by side, and the sheet is drawn
  // once they have all answered: a band that arrived on its own would push the
  // sheet, and the log below it on a phone, down after first paint.
  const [overdue, due, week, waiting, projects] = useSuspenseQueries({
    queries: [
      actionable({ overdue: true, limit: PREVIEW_ROWS }),
      actionable({ due_from: today(), due_to: today(), limit: PREVIEW_ROWS }),
      actionable({ due_from: tomorrow(), due_to: inAWeek(), limit: 1 }),
      // Soonest first, undated last: the API sorts a missing date to the end.
      tasksIn(WAITING, { sort: "due_date", limit: PREVIEW_ROWS }),
      projectsQuery(),
    ],
  })

  const names = Object.fromEntries(
    projects.data.data.map((project) => [project.id, project.name]),
  )
  const overdueCount = overdue.data.count
  const dueCount = due.data.count
  const weekCount = week.data.count
  const waitingCount = waiting.data.count
  const clear = overdueCount === 0 && dueCount === 0

  return (
    <div className="bg-card overflow-hidden rounded-lg border">
      {clear ? (
        <Group label="Due today" count={0}>
          <div className="flex flex-col items-center gap-2 px-6 py-12 text-center">
            <CheckCheck className="text-muted-foreground size-6" aria-hidden />
            <p className="font-medium">You are all clear</p>
            <p className="text-muted-foreground max-w-xs text-sm">
              {weekCount > 0
                ? `${weekCount} ${weekCount === 1 ? "task is" : "tasks are"} due later this week.`
                : "Nothing is waiting in the next seven days either."}
            </p>
          </div>
        </Group>
      ) : (
        <>
          {overdueCount > 0 && (
            <Group label="Overdue" count={overdueCount} tone="alert">
              {overdue.data.data.map((task) => (
                <CompactTaskRow
                  key={task.id}
                  task={task}
                  projectName={names[task.project_id]}
                />
              ))}
              {overdueCount > PREVIEW_ROWS && (
                <MoreLink
                  count={overdueCount - PREVIEW_ROWS}
                  search={{ overdue: true, status: ACTIONABLE }}
                />
              )}
            </Group>
          )}

          {dueCount > 0 && (
            <Group label="Due today" count={dueCount}>
              {due.data.data.map((task) => (
                <CompactTaskRow
                  key={task.id}
                  task={task}
                  projectName={names[task.project_id]}
                />
              ))}
              {dueCount > PREVIEW_ROWS && (
                <MoreLink
                  count={dueCount - PREVIEW_ROWS}
                  search={{
                    due_from: today(),
                    due_to: today(),
                    status: ACTIONABLE,
                  }}
                />
              )}
            </Group>
          )}
        </>
      )}

      {weekCount > 0 && !clear && (
        <RouterLink
          to="/tasks"
          search={{
            due_from: tomorrow(),
            due_to: inAWeek(),
            status: ACTIONABLE,
          }}
          className="hover:bg-muted/50 flex items-center justify-between gap-2 border-t px-4 py-3 text-sm transition-colors"
        >
          <span className="text-muted-foreground">
            {weekCount} more due later this week
          </span>
          <ArrowRight className="text-muted-foreground size-4" aria-hidden />
        </RouterLink>
      )}

      {/* After This week, and only when something is waiting: what the owner
          has to chase rather than do. It stands whether or not the rest is
          clear, since being clear of work is not being clear of waits. */}
      {waitingCount > 0 && (
        <div className="border-t">
          <Group label="Waiting on others" count={waitingCount}>
            {waiting.data.data.map((task) => (
              <CompactTaskRow
                key={task.id}
                task={task}
                projectName={names[task.project_id]}
              />
            ))}
            <MoreLink
              count={waitingCount - PREVIEW_ROWS}
              label="See all"
              search={{ status: WAITING, sort: "due_date" }}
            />
          </Group>
        </div>
      )}
    </div>
  )
}
