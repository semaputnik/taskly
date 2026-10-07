import { useQuery } from "@tanstack/react-query"
import { ChevronRight } from "lucide-react"

import type { TaskPublic } from "@/client"
import { useRecordPanel } from "@/components/Records/panels"
import {
  EditableText,
  RecordPanel,
  TitleRow,
  taskTitleClass,
} from "@/components/Records/RecordPanel"
import { useWalk } from "@/components/Records/walk"
import { formatDayOf, inSentence } from "@/lib/dates"
import { projectsQuery, taskQuery } from "@/lib/serverState"
import { toastSuccess } from "@/lib/toasts"
import { cn } from "@/lib/utils"
import { CompleteTask } from "./CompleteTask"
import { useCaptureTarget } from "./capture"
import DeleteTask from "./DeleteTask"
import { NewTask } from "./NewTask"
import { TaskActivity } from "./TaskActivity"
import { TaskAttachments } from "./TaskAttachments"
import { reporterName, TaskProperties } from "./TaskProperties"
import { TaskSubtasks } from "./TaskSubtasks"
import { useTaskUpdate } from "./useTaskWrites"

/**
 * Everything one task is and has, in a single panel.
 *
 * Before this, a task's comments, files, subtasks and fields each lived behind
 * their own entry in a row menu, so reading a task meant opening four dialogs
 * in turn and holding the result in your head. The panel is the task's one
 * address — and it is a real address: it is driven by the URL, so an activity
 * entry or the dashboard can link straight to a task rather than dropping the
 * reader on the unfiltered list.
 */
export function TaskDetail() {
  // Fetched by id rather than read out of the table: a link may point at a
  // task the current filters exclude, and it must still open.
  const {
    id: taskId,
    capturing,
    record: task,
    panels,
    shell,
  } = useRecordPanel("task")
  const captureTarget = useCaptureTarget()
  const onOpenTask = panels.openTask
  // The list the task was opened from, when there is one to walk.
  const walk = useWalk(taskId)

  const { data: projects } = useQuery({
    ...projectsQuery(),
    enabled: Boolean(taskId),
  })
  // The parent by its own address, which is also where its panel reads it,
  // so following the breadcrumb opens it from the cache.
  const parentId = task?.parent_id
  const { data: parent } = useQuery(taskQuery(parentId))

  const projectName = task
    ? projects?.data.find((p) => p.id === task.project_id)?.name
    : undefined

  return (
    <RecordPanel
      {...shell}
      walk={walk}
      onWalk={panels.walkTo}
      destructive={
        task && !capturing ? (
          <DeleteTask task={task} onSuccess={shell.onClose} />
        ) : undefined
      }
      bar={
        capturing ? (
          <>
            <span className="shrink-0">New task</span>
            <span aria-hidden>·</span>
            <span className="truncate">Not saved yet</span>
          </>
        ) : task ? (
          <>
            {/* On a phone the project is left for a screen reader, as in the
                other columns' bars: the Project row says it, and the date
                needs the room to stay whole beside the walk count. */}
            <span className="text-ink-2 shrink-0 font-medium max-sm:sr-only">
              {projectName ?? "Inbox"}
            </span>
            {parent && (
              <>
                <ChevronRight
                  className="size-3.5 shrink-0 max-sm:hidden"
                  aria-hidden
                />
                <button
                  type="button"
                  onClick={() => onOpenTask(parent.id)}
                  className="hover:text-foreground focus-visible:ring-ring/50 min-w-0 truncate rounded-sm underline-offset-4 outline-none hover:underline focus-visible:ring-[3px]"
                >
                  {parent.title}
                </button>
              </>
            )}
            <span aria-hidden className={cn(!parent && "max-sm:hidden")}>
              ·
            </span>
            <span className="shrink-0 whitespace-nowrap">{opened(task)}</span>
          </>
        ) : undefined
      }
    >
      {capturing ? (
        <NewTask
          target={captureTarget}
          onCreated={(created, stay) => {
            // A run of captures holds the panel still. A single one is done:
            // the panel closes on the screen it was opened over, and the
            // notice is the receipt, with the way to the record it made.
            if (stay) return
            panels.close()
            toastSuccess(`“${created.title}” created`, {
              label: "Open",
              onClick: () => panels.openTask(created.id),
            })
          }}
        />
      ) : !task ? null : (
        <>
          {/* The status mark is the control that closes the task, beside the
              title it closes. */}
          <TitleRow
            mark={
              <CompleteTask
                asMark
                announce
                task={task}
                markClassName="size-[22px]"
                // 22px mark, 11px of padding each side: the 44px a thumb needs,
                // taken back out of the margin so nothing moves.
                className="pointer-coarse:-m-[11px] pointer-coarse:p-[11px]"
              />
            }
          >
            <TaskTitle task={task} />
          </TitleRow>

          <TaskProperties task={task} />

          <TaskSubtasks
            key={`subtasks-${task.id}`}
            task={task}
            onOpen={onOpenTask}
          />
          <TaskAttachments key={`files-${task.id}`} task={task} />
          <TaskActivity key={`activity-${task.id}`} task={task} />
        </>
      )}
    </RecordPanel>
  )
}

/**
 * The bar's account of how the task came to be: "opened by you, 24 Sept",
 * or by the bot user that filed it. A task from before the reporter was kept
 * says only when. The day is said in words, as the Created row beneath says its day (it
 * adds the time).
 */
function opened(task: TaskPublic): string {
  const by = reporterName(task)
  const day = task.created_at ? inSentence(formatDayOf(task.created_at)) : null
  return ["opened", by && `by ${by},`, day].filter(Boolean).join(" ")
}

/** The task's own name, saved when focus leaves it. */
function TaskTitle({ task }: { task: TaskPublic }) {
  const update = useTaskUpdate(task)

  return (
    <EditableText
      wrap
      value={task.title}
      ariaLabel="Task title"
      required="A task needs a title"
      onCommit={(title) => update.save({ title: title.trim() })}
      className={taskTitleClass}
    />
  )
}
