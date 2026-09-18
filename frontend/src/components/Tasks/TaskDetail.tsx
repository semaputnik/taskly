import { useQuery } from "@tanstack/react-query"
import { ChevronRight } from "lucide-react"

import type { TaskPublic } from "@/client"
import { useRecordPanel } from "@/components/Records/panels"
import {
  EditableText,
  RecordHeader,
  RecordPanel,
  titleFieldClass,
} from "@/components/Records/RecordPanel"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  projectsQuery,
  taskQuery,
  tasksQuery,
  useReportChange,
} from "@/lib/serverState"
import { CompleteTask } from "./CompleteTask"
import { CaptureField, useCaptureTarget } from "./capture"
import DeleteTask from "./DeleteTask"
import { NewTask } from "./NewTask"
import { PriorityBadge } from "./priority"
import { TaskAttachments } from "./TaskAttachments"
import { TaskComments } from "./TaskComments"
import { TaskProperties } from "./TaskProperties"
import { useTaskCapture, useTaskUpdate } from "./useTaskWrites"

/** More than a panel should list; past it, the tab says how many there are. */
const SUBTASK_LIMIT = 100

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

  const { data: projects } = useQuery({
    ...projectsQuery(),
    enabled: Boolean(taskId),
  })
  // Subtasks are not a nested field, so the panel asks for this task's
  // children alone: a task list like any other, refreshed with them.
  const { data: subtasks } = useQuery({
    ...tasksQuery({ parent_id: taskId, limit: SUBTASK_LIMIT }),
    enabled: Boolean(taskId),
  })
  // The parent by its own address, which is also where its panel reads it,
  // so following the breadcrumb opens it from the cache.
  const parentId = task?.parent_id
  const { data: parent } = useQuery(taskQuery(parentId))

  const projectName = task
    ? projects?.data.find((p) => p.id === task.project_id)?.name
    : undefined
  const children: TaskPublic[] = subtasks?.data ?? []
  const childCount = subtasks?.count ?? 0

  return (
    <RecordPanel
      {...shell}
      destructive={
        task && !capturing ? (
          <DeleteTask task={task} onSuccess={shell.onClose} />
        ) : undefined
      }
    >
      {capturing ? (
        <NewTask
          target={captureTarget}
          onCreated={(created, stay) => {
            // A run of captures holds the panel still; a single one hands the
            // reader the record it just made, at its own address.
            if (!stay) panels.openTask(created.id)
          }}
        />
      ) : !task ? null : (
        <>
          <RecordHeader
            breadcrumb={
              <>
                <span className="shrink-0">{projectName ?? "Inbox"}</span>
                {parent && (
                  <>
                    <ChevronRight className="size-3.5 shrink-0" aria-hidden />
                    <button
                      type="button"
                      onClick={() => onOpenTask(parent.id)}
                      className="hover:text-foreground truncate underline-offset-4 transition-colors hover:underline"
                    >
                      {parent.title}
                    </button>
                  </>
                )}
              </>
            }
            title={
              <div className="flex items-start gap-3">
                <span className="mt-2.5">
                  <CompleteTask task={task} />
                </span>
                <TaskTitle task={task} />
              </div>
            }
          />

          <TaskProperties task={task} />

          <Tabs
            defaultValue="comments"
            className="gap-4 border-t px-6 py-5"
            // A tab's content is mounted only while it is on screen, so a
            // collection is fetched only once its tab is opened; each task
            // starts on its comments.
            key={task.id}
          >
            <TabsList>
              <TabsTrigger value="comments">Comments</TabsTrigger>
              <TabsTrigger value="subtasks">
                Subtasks
                {childCount > 0 && (
                  <span className="text-muted-foreground tabular-nums">
                    {childCount}
                  </span>
                )}
              </TabsTrigger>
              <TabsTrigger value="files">Files</TabsTrigger>
            </TabsList>

            <TabsContent value="comments">
              <TaskComments task={task} />
            </TabsContent>

            <TabsContent value="subtasks" className="flex flex-col gap-3">
              {children.length ? (
                <ul className="flex flex-col gap-2">
                  {children.map((child) => (
                    <li
                      key={child.id}
                      className="flex items-center gap-3 rounded-md border px-3 py-2"
                    >
                      <CompleteTask task={child} />
                      <button
                        type="button"
                        onClick={() => onOpenTask(child.id)}
                        className={`min-w-0 flex-1 truncate text-left text-sm underline-offset-4 hover:underline ${
                          child.status === "done"
                            ? "text-muted-foreground line-through"
                            : ""
                        }`}
                      >
                        {child.title}
                      </button>
                      {child.priority && (
                        <PriorityBadge
                          priority={child.priority}
                          className="shrink-0"
                        />
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-muted-foreground text-sm italic">
                  No subtasks yet.
                </p>
              )}
              {childCount > children.length && (
                <p className="text-muted-foreground text-sm">
                  Showing the first {children.length} of {childCount} subtasks.
                </p>
              )}
              {/* Adding a subtask belongs with the subtasks, not in a menu
                    somewhere else on the panel. It stays one field: the reader
                    is working down a list here, and each child opens as a full
                    task to set the rest. */}
              <SubtaskCapture parent={task} />
            </TabsContent>

            <TabsContent value="files">
              <TaskAttachments task={task} />
            </TabsContent>
          </Tabs>
        </>
      )}
    </RecordPanel>
  )
}

/** The task's own name, saved when focus leaves it. */
function TaskTitle({ task }: { task: TaskPublic }) {
  const update = useTaskUpdate(task)

  return (
    <EditableText
      value={task.title}
      ariaLabel="Task title"
      onCommit={(title) =>
        title.trim() ? update.save({ title: title.trim() }) : undefined
      }
      className={titleFieldClass}
    />
  )
}

/**
 * One-field capture for a child of the open task.
 *
 * It sits beneath the subtasks, where the reader already is when they decide
 * to add one, and it leaves them there: the child appears in the list above
 * and the parent stays open. The child holds no project of its own — it
 * belongs to the project of its root task (FR-02.4).
 */
function SubtaskCapture({ parent }: { parent: TaskPublic }) {
  const reportChange = useReportChange()
  const capture = useTaskCapture(
    { parentId: parent.id, projectName: "Follows its parent task" },
    () => {
      // The panel's children are a task list query, so that is what has to
      // catch up; the reader is not moved onto the child.
      reportChange({ type: "task created" })
    },
  )

  return (
    <>
      <CaptureField
        staysOpen
        label="Subtask title"
        placeholder="Add a subtask"
        onCommit={capture.create}
      />
      <output aria-live="polite" className="sr-only">
        {capture.announcement}
      </output>
    </>
  )
}
