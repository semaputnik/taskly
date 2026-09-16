import { useQuery, useQueryClient } from "@tanstack/react-query"
import { ChevronRight } from "lucide-react"

import { ProjectsService, type TaskPublic, TasksService } from "@/client"
import {
  EditableText,
  RecordHeader,
  RecordPanel,
  recordLoad,
  titleFieldClass,
} from "@/components/Records/RecordPanel"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { CompleteTask } from "./CompleteTask"
import { CaptureField, type CaptureTarget, useTaskCapture } from "./capture"
import DeleteTask from "./DeleteTask"
import { NewTask } from "./NewTask"
import { TaskAttachments } from "./TaskAttachments"
import { TaskComments } from "./TaskComments"
import { TaskProperties } from "./TaskProperties"
import { useTaskUpdate } from "./useTaskUpdate"

interface TaskDetailProps {
  /** The task to show, or null for a closed panel. */
  taskId: string | null
  /** Open on a task that does not exist yet, ready to capture one. */
  capturing?: boolean
  /** Where a captured task lands, named on screen before it is created. */
  captureTarget?: CaptureTarget
  onClose: () => void
  /** Move the panel to another task without closing it. */
  onOpenTask: (taskId: string) => void
  /**
   * A task has just been captured. `stay` is set when the reader asked to keep
   * capturing, so the panel holds still instead of moving onto the record.
   */
  onCaptured?: (taskId: string, stay: boolean) => void
}

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
export function TaskDetail({
  taskId,
  capturing = false,
  captureTarget,
  onClose,
  onOpenTask,
  onCaptured,
}: TaskDetailProps) {
  // Capture is the panel one step earlier, so it opens the same surface. The
  // record itself is only fetched once there is one.
  const isCapturing = capturing && !taskId
  const isOpen = Boolean(taskId) || capturing

  // Fetched by id rather than read out of the table: a link may point at a
  // task the current filters exclude, and it must still open.
  const query = useQuery({
    queryKey: ["task", taskId],
    queryFn: async () =>
      (await TasksService.readTask({ path: { task_id: taskId as string } }))
        .data,
    enabled: Boolean(taskId),
  })
  const task = query.data

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: async () =>
      (await ProjectsService.readProjects({ query: { skip: 0, limit: 100 } }))
        .data,
    enabled: Boolean(taskId),
  })
  // Subtasks are not a nested field, so the panel finds this task's children
  // in the list.
  const { data: all } = useQuery({
    queryKey: ["tasks", { skip: 0, limit: 200 }],
    queryFn: async () =>
      (await TasksService.readTasks({ query: { skip: 0, limit: 200 } })).data,
    enabled: Boolean(taskId),
  })

  const projectName = task
    ? projects?.data.find((p) => p.id === task.project_id)?.name
    : undefined
  const parent = task?.parent_id
    ? all?.data.find((t) => t.id === task.parent_id)
    : undefined
  const children: TaskPublic[] = task
    ? (all?.data ?? []).filter((t) => t.parent_id === task.id)
    : []

  return (
    <RecordPanel
      open={isOpen}
      onClose={onClose}
      name={isCapturing ? "New task" : (task?.title ?? "Task")}
      kind="task"
      {...recordLoad(query, !isCapturing && Boolean(taskId))}
      destructive={
        task && !isCapturing ? (
          <DeleteTask task={task} onSuccess={onClose} />
        ) : undefined
      }
    >
      {isCapturing && captureTarget ? (
        <NewTask
          target={captureTarget}
          onCreated={(created, stay) => onCaptured?.(created.id, stay)}
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
                {children.length > 0 && (
                  <span className="text-muted-foreground tabular-nums">
                    {children.length}
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
                          child.completed
                            ? "text-muted-foreground line-through"
                            : ""
                        }`}
                      >
                        {child.title}
                      </button>
                      {child.priority && (
                        <Badge variant="outline" className="shrink-0">
                          {child.priority}
                        </Badge>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-muted-foreground text-sm italic">
                  No subtasks yet.
                </p>
              )}
              {/* Adding a subtask belongs with the subtasks, not in a menu
                    somewhere else on the panel — and it is the same one-field
                    capture as anywhere else, because a subtask is a full task
                    rather than a checklist item. */}
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
      onCommit={(title) => {
        if (title.trim()) update.save({ title: title.trim() })
      }}
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
  const queryClient = useQueryClient()
  const capture = useTaskCapture(
    { parentId: parent.id, projectName: "Follows its parent task" },
    () => {
      // The panel finds its children in the task list, so that is what has to
      // catch up; the reader is not moved onto the child.
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
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
