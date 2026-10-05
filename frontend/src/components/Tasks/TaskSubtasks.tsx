import { useQuery } from "@tanstack/react-query"

import type { TaskPublic } from "@/client"
import { RecordSection } from "@/components/Records/RecordPanel"
import { isoDay } from "@/lib/dates"
import { tasksQuery, useReportChange } from "@/lib/serverState"
import { cn } from "@/lib/utils"
import { CompleteTask } from "./CompleteTask"
import { CaptureField } from "./capture"
import { describeDue } from "./compact"
import { useTaskCapture } from "./useTaskWrites"

/** More than a panel should list; past it, the section says how many there are. */
const SUBTASK_LIMIT = 100

/**
 * A task's subtasks, one line each, and the field that adds the next.
 *
 * Subtasks are not a nested field, so the section asks for this task's
 * children alone: a task list like any other, refreshed with them. The count
 * in the heading is how far through them the task is (FR-02.9), read off the
 * same list, so closing a line moves it at once.
 */
export function TaskSubtasks({
  task,
  onOpen,
}: {
  task: TaskPublic
  onOpen: (id: string) => void
}) {
  const { data } = useQuery(
    tasksQuery({ parent_id: task.id, limit: SUBTASK_LIMIT }),
  )
  const children = data?.data ?? []
  const total = data?.count ?? 0
  const done = children.filter((child) => child.status === "done").length
  const today = isoDay(new Date())

  return (
    <RecordSection
      title="Subtasks"
      count={total > 0 ? `${done}/${total}` : undefined}
    >
      <ul>
        {children.map((child) => (
          <SubtaskLine
            key={child.id}
            task={child}
            today={today}
            onOpen={onOpen}
          />
        ))}
      </ul>
      {total > children.length && (
        <p className="text-ink-3 pt-2 text-[13px]">
          Showing the first {children.length} of {total} subtasks.
        </p>
      )}
      <SubtaskCapture parent={task} />
    </RecordSection>
  )
}

/**
 * One child: the status mark that closes it, its title that opens it, and one
 * quiet fact at the right — the day it is due, else the bot user it is with.
 */
function SubtaskLine({
  task,
  today,
  onOpen,
}: {
  task: TaskPublic
  today: string
  onOpen: (id: string) => void
}) {
  const closed = task.status === "done"
  const due = task.due_date
    ? describeDue(task.due_date, today, { done: closed })
    : null
  const fact = due?.text ?? task.assignee_bot_user?.name

  return (
    <li className="border-rule grid min-h-9 grid-cols-[18px_minmax(0,1fr)_auto] items-center gap-3 border-b py-px">
      <span className="flex">
        <CompleteTask asMark task={task} />
      </span>
      <button
        type="button"
        onClick={() => onOpen(task.id)}
        className={cn(
          "focus-visible:ring-ring/50 max-w-full min-w-0 justify-self-start truncate rounded-sm text-left text-sm font-medium underline-offset-4 outline-none hover:underline focus-visible:ring-[3px] pointer-coarse:min-h-11",
          closed && "text-ink-3 font-normal line-through",
        )}
      >
        {task.title}
      </button>
      {fact && (
        <span
          className={cn(
            "text-ink-3 text-[12.5px]",
            due?.tone === "late" && "text-late",
          )}
        >
          {fact}
        </span>
      )}
    </li>
  )
}

/**
 * The line at the end of the list that adds a child.
 *
 * Enter creates it right there with defaults — Backlog, the parent's project
 * and nothing else — the line appears above and the field stays for the next
 * one; nothing opens. A refusal hands the title back. The child holds no
 * project of its own: it belongs to the project of its root task (FR-02.4).
 */
function SubtaskCapture({ parent }: { parent: TaskPublic }) {
  const reportChange = useReportChange()
  const capture = useTaskCapture(
    { parentId: parent.id, projectName: "Follows its parent task" },
    () => {
      // The section's children are a task list query, so that is what has to
      // catch up; the reader is not moved onto the child.
      reportChange({ type: "task created" })
    },
  )

  return (
    <div className="border-rule grid min-h-9 grid-cols-[18px_minmax(0,1fr)_auto] items-center gap-3 border-b">
      <span
        aria-hidden
        className="border-rule-strong size-[18px] rounded-full border-[1.5px]"
      />
      <CaptureField
        staysOpen
        label="New subtask"
        placeholder="Add a subtask…"
        onCommit={capture.create}
        className="placeholder:text-ink-3 h-9 rounded-sm border-0 bg-transparent px-0 shadow-none dark:bg-transparent"
      />
      <span
        aria-hidden
        className="text-ink-3 hidden text-xs opacity-80 sm:inline"
      >
        Enter creates it here
      </span>
      <output aria-live="polite" className="sr-only">
        {capture.announcement}
      </output>
    </div>
  )
}
