import {
  useQueries,
  useQuery,
  useSuspenseQueries,
  useSuspenseQuery,
} from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"

import type { TaskHandover, TaskPublic } from "@/client"
import {
  CompactTaskRow,
  CompactTaskRowPending,
} from "@/components/Tasks/CompactTaskRow"
import { completionReceipt } from "@/components/Tasks/CompleteTask"
import { useTaskStatus } from "@/components/Tasks/useTaskWrites"
import { Skeleton } from "@/components/ui/skeleton"
import { currentUserQuery, projectsQuery, tasksQuery } from "@/lib/serverState"
import { cn } from "@/lib/utils"
import {
  handoverLine,
  MY_WORK_GROUPS,
  MY_WORK_PREVIEW,
  type MyWorkStatus,
  myWorkSearch,
} from "./work"

/**
 * In my hands: the reader's My work (FR-06.7). The tasks whose assignee is
 * the reader themselves, grouped by status in the order work moves, most
 * pressing first. Unassigned work, work on a bot user and Backlog are the
 * Tasks page's; this is what is on the reader now.
 */

/** One request per group, so each knows its own count. */
const myWorkQueries = (userId: string) =>
  MY_WORK_GROUPS.map(({ status }) =>
    tasksQuery({
      assignee_id: userId,
      status: [status],
      sort: "priority",
      limit: MY_WORK_PREVIEW,
    }),
  )

/**
 * Start the groups' requests beside the rest of the page's, rather than
 * once the sections before them have resumed. Waits on nothing: until the
 * reader is known, it asks for nothing.
 */
export function usePrefetchMyWork() {
  const { data: user } = useQuery(currentUserQuery())
  useQueries({ queries: user ? myWorkQueries(user.id) : [] })
}

const textLink =
  "focus-visible:ring-ring/50 rounded-sm underline-offset-[3px] outline-none hover:underline focus-visible:ring-[3px]"

function Heading({ count }: { count: number | null }) {
  return (
    <h2 className="border-rule-strong flex items-baseline gap-2 border-b pb-2 text-[13px] font-semibold">
      In my hands
      {count !== null && (
        <span className="text-ink-3 font-mono text-xs font-normal">
          {count}
        </span>
      )}
      <span className="text-ink-3 ml-auto font-normal">assigned to you</span>
    </h2>
  )
}

/** The panel while its tasks are on their way: the same shape. */
export function MyWorkPending() {
  return (
    <section className="mb-9">
      <Heading count={null} />
      <div className="mt-[22px]">
        <Skeleton className="mb-1 ml-[30px] h-3 w-20" />
        {Array.from({ length: 2 }).map((_, index) => (
          <CompactTaskRowPending key={index} flush />
        ))}
      </div>
    </section>
  )
}

export function MyWork() {
  const { data: user } = useSuspenseQuery(currentUserQuery())
  // The projects are the bands' own request, already in the cache.
  const projects = useSuspenseQuery(projectsQuery())
  const groups = useSuspenseQueries({ queries: myWorkQueries(user.id) })
  const projectNames: Record<string, string> = Object.fromEntries(
    projects.data.data.map((project) => [project.id, project.name]),
  )
  const total = groups.reduce((sum, group) => sum + group.data.count, 0)

  return (
    <section className="mb-9">
      <Heading count={total} />
      {total === 0 ? (
        // Drawn even when empty: the page keeps its shape from day to day.
        <p className="text-ink-2 pt-3">Nothing is in your hands right now.</p>
      ) : (
        MY_WORK_GROUPS.map(({ status, label }, index) => {
          const { data, count } = groups[index].data
          if (count === 0) return null
          return (
            <StatusGroup
              key={status}
              status={status}
              label={label}
              count={count}
              tasks={data}
              projectNames={projectNames}
            />
          )
        })
      )}
    </section>
  )
}

function StatusGroup({
  status,
  label,
  count,
  tasks,
  projectNames,
}: {
  status: MyWorkStatus
  label: string
  count: number
  tasks: TaskPublic[]
  projectNames: Record<string, string>
}) {
  return (
    <section className="mt-[22px]">
      <h3 className="text-ink-3 pb-1 pl-[30px] text-[13px] font-medium">
        {label}
      </h3>
      {tasks.map((task) => (
        <CompactTaskRow
          key={task.id}
          task={task}
          projectName={projectNames[task.project_id]}
          receipt
          flush
        >
          {task.handover && <Handover task={task} handover={task.handover} />}
        </CompactTaskRow>
      ))}
      {count > tasks.length && (
        <RouterLink
          to="/tasks"
          search={myWorkSearch(status)}
          className={cn(
            textLink,
            "text-ink-3 inline-block pt-2 pl-[30px] text-[13px]",
          )}
        >
          {count - tasks.length} more <span aria-hidden>→</span>
        </RouterLink>
      )}
    </section>
  )
}

/**
 * The bot user's hand-over, under the task it finished: who, when, and the
 * one way to act on it here — close it. Sending it back is the task's own
 * business, in its panel.
 */
function Handover({
  task,
  handover,
}: {
  task: TaskPublic
  handover: TaskHandover
}) {
  const status = useTaskStatus(task, {
    onCompleted: completionReceipt(task),
  })
  const { who, rest } = handoverLine(handover, new Date())

  return (
    <div className="text-ink-3 mt-1.5 flex flex-wrap items-center gap-x-3.5 gap-y-1 text-[0.8125rem] leading-tight">
      <span>
        <span className="text-ink-2 font-medium">{who}</span> {rest}
      </span>
      <button
        type="button"
        disabled={status.isPending}
        onClick={() => void status.change("done")}
        aria-label={`Close it: ${task.title}`}
        className={cn(textLink, "text-done font-medium disabled:opacity-50")}
      >
        Close it
      </button>
      {status.prompt}
    </div>
  )
}
