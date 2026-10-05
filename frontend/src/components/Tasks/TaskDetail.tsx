import { useQuery } from "@tanstack/react-query"
import { ChevronRight } from "lucide-react"

import type { TaskPublic } from "@/client"
import { useRecordPanel } from "@/components/Records/panels"
import {
  EditableText,
  RecordPanel,
  RecordSection,
  TitleRow,
  taskTitleClass,
} from "@/components/Records/RecordPanel"
import { useWalk } from "@/components/Records/walk"
import { formatDayOf } from "@/lib/dates"
import { projectsQuery, taskQuery } from "@/lib/serverState"
import { toastSuccess } from "@/lib/toasts"
import { CompleteTask } from "./CompleteTask"
import { useCaptureTarget } from "./capture"
import DeleteTask from "./DeleteTask"
import { NewTask } from "./NewTask"
import { TaskAttachments } from "./TaskAttachments"
import { TaskComments } from "./TaskComments"
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
            <span className="text-ink-2 shrink-0 font-medium">
              {projectName ?? "Inbox"}
            </span>
            {parent && (
              <>
                <ChevronRight className="size-3.5 shrink-0" aria-hidden />
                <button
                  type="button"
                  onClick={() => onOpenTask(parent.id)}
                  className="hover:text-foreground focus-visible:ring-ring/50 min-w-0 truncate rounded-sm underline-offset-4 outline-none hover:underline focus-visible:ring-[3px]"
                >
                  {parent.title}
                </button>
              </>
            )}
            <span aria-hidden>·</span>
            <span className="truncate">{opened(task)}</span>
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
              <CompleteTask asMark task={task} markClassName="size-[22px]" />
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
          {/* Kept as it was, for now; the Activity section replaces it. */}
          <RecordSection title="Comments">
            <div className="pt-2">
              <TaskComments key={task.id} task={task} />
            </div>
          </RecordSection>
        </>
      )}
    </RecordPanel>
  )
}

/**
 * The bar's account of how the task came to be: "opened by you, 24.09.2026",
 * or by the bot user that filed it. A task from before the reporter was kept
 * says only when. The day is written the product's way, numerically in the
 * reader's locale, as the Created row beneath writes its day (it adds the time).
 */
function opened(task: TaskPublic): string {
  const by = reporterName(task)
  const day = task.created_at ? formatDayOf(task.created_at) : null
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
      onCommit={(title) =>
        title.trim() ? update.save({ title: title.trim() }) : undefined
      }
      className={taskTitleClass}
    />
  )
}
