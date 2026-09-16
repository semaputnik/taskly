import { useQuery } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import { ArrowRight, CheckCheck } from "lucide-react"

import { ProjectsService, type TaskPublic, TasksService } from "@/client"
import { CompleteTask } from "@/components/Tasks/CompleteTask"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import { daysLate, inAWeek, today, tomorrow } from "./when"

const PREVIEW_ROWS = 5

function openTasks(query: Record<string, unknown>) {
  return {
    queryKey: ["tasks", query],
    queryFn: async () =>
      (await TasksService.readTasks({ query: { ...query, completed: false } }))
        .data,
  }
}

/**
 * A band of rows under its own label. Group headers borrow the table's
 * uppercase micro type because that is exactly what they are — a header over
 * a set of rows — and inventing a second treatment for the same job would
 * read as an inconsistency, not a distinction.
 */
function Group({
  label,
  count,
  tone = "default",
  children,
}: {
  label: string
  count: number
  tone?: "default" | "alert"
  children: React.ReactNode
}) {
  return (
    <section>
      <h2 className="bg-muted/50 flex items-center gap-2 border-b px-4 py-2.5 text-xs font-semibold tracking-wider uppercase">
        <span className={cn(tone === "alert" && "text-destructive")}>
          {label}
        </span>
        <span className="text-muted-foreground font-normal tabular-nums">
          {count}
        </span>
      </h2>
      {children}
    </section>
  )
}

function TaskRow({
  task,
  projectName,
  trailing,
}: {
  task: TaskPublic
  projectName?: string
  trailing?: React.ReactNode
}) {
  return (
    <div className="hover:bg-muted/50 flex items-center gap-3 border-b px-4 py-3 transition-colors last:border-b-0">
      <CompleteTask task={task} />
      {/* The title is the link, not the whole row: the row also holds the
          completion control, and a checkbox inside a link is a trap. */}
      <RouterLink
        to="/"
        search={{ task: task.id }}
        className="min-w-0 flex-1 truncate text-sm font-medium underline-offset-4 hover:underline"
      >
        {task.title}
      </RouterLink>
      {projectName && (
        <span className="text-muted-foreground hidden text-sm sm:inline">
          {projectName}
        </span>
      )}
      <span className="w-8 shrink-0 text-right">
        {task.priority && <Badge variant="outline">{task.priority}</Badge>}
      </span>
      {/* Reserved whether or not this group has anything to put here, so the
          priority column stays put from one group to the next. */}
      <span className="w-20 shrink-0 text-right text-xs whitespace-nowrap">
        {trailing}
      </span>
    </div>
  )
}

function Rows({ count }: { count: number }) {
  return Array.from({ length: count }).map((_, index) => (
    <div key={index} className="flex items-center gap-3 border-b px-4 py-3">
      <Skeleton className="size-4 rounded-[4px]" />
      <Skeleton className="h-4 w-48" />
    </div>
  ))
}

/**
 * The work the day is actually asking for: what is late, what is due today,
 * and how much is waiting behind them. It is a preview, not the task list —
 * anything longer than a few rows hands off to Tasks.
 */
export function NeedsYou() {
  const overdue = useQuery(openTasks({ overdue: true, limit: PREVIEW_ROWS }))
  const due = useQuery(
    openTasks({ due_from: today(), due_to: today(), limit: PREVIEW_ROWS }),
  )
  const week = useQuery(
    openTasks({ due_from: tomorrow(), due_to: inAWeek(), limit: 1 }),
  )
  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: async () =>
      (await ProjectsService.readProjects({ query: { skip: 0, limit: 100 } }))
        .data,
  })

  const names = Object.fromEntries(
    (projects?.data ?? []).map((project) => [project.id, project.name]),
  )
  const isPending = overdue.isPending || due.isPending
  const overdueCount = overdue.data?.count ?? 0
  const dueCount = due.data?.count ?? 0
  const weekCount = week.data?.count ?? 0
  const clear = !isPending && overdueCount === 0 && dueCount === 0

  return (
    <div className="bg-card overflow-hidden rounded-lg border">
      {isPending ? (
        <>
          <Group label="Overdue" count={0}>
            <Rows count={2} />
          </Group>
          <Group label="Due today" count={0}>
            <Rows count={2} />
          </Group>
        </>
      ) : clear ? (
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
              {overdue.data?.data.map((task) => (
                <TaskRow
                  key={task.id}
                  task={task}
                  projectName={names[task.project_id]}
                  trailing={
                    task.due_date && (
                      <span className="text-destructive">
                        {daysLate(task.due_date)}
                      </span>
                    )
                  }
                />
              ))}
              {overdueCount > PREVIEW_ROWS && (
                <MoreLink
                  count={overdueCount - PREVIEW_ROWS}
                  search={{ overdue: true, completed: false }}
                />
              )}
            </Group>
          )}

          {dueCount > 0 && (
            <Group label="Due today" count={dueCount}>
              {due.data?.data.map((task) => (
                <TaskRow
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
                    completed: false,
                  }}
                />
              )}
            </Group>
          )}
        </>
      )}

      {!isPending && weekCount > 0 && !clear && (
        <RouterLink
          to="/tasks"
          search={{ due_from: tomorrow(), due_to: inAWeek(), completed: false }}
          className="hover:bg-muted/50 flex items-center justify-between gap-2 border-t px-4 py-3 text-sm transition-colors"
        >
          <span className="text-muted-foreground">
            {weekCount} more due later this week
          </span>
          <ArrowRight className="text-muted-foreground size-4" aria-hidden />
        </RouterLink>
      )}
    </div>
  )
}

function MoreLink({
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
      className="text-muted-foreground hover:bg-muted/50 hover:text-foreground flex items-center gap-1.5 border-b px-4 py-2.5 text-sm transition-colors last:border-b-0"
    >
      {count} more
      <ArrowRight className="size-3.5" aria-hidden />
    </RouterLink>
  )
}
