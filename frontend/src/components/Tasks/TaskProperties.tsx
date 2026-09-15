import { useQuery } from "@tanstack/react-query"
import {
  Calendar,
  CircleCheck,
  CircleDashed,
  Clock,
  Flag,
  FolderKanban,
  type LucideIcon,
  Repeat,
  Tag,
  User as UserIcon,
} from "lucide-react"
import { useEffect, useId, useState } from "react"

import {
  ProjectsService,
  type RecurrenceFrequency,
  type TaskPublic,
  type TaskUpdate,
} from "@/client"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import useAuth from "@/hooks/useAuth"
import { cn } from "@/lib/utils"
import { AssigneeSelect, assigneeFormValue, toAssigneeId } from "./assignee"
import { CompleteTask } from "./CompleteTask"
import { DueDateScopeDialog, NO_RECURRENCE } from "./recurrence"
import { TagsField } from "./TagsField"
import { useTaskUpdate } from "./useTaskUpdate"

const NO_PRIORITY = "none"

/**
 * Controls in the panel are flat until you reach for them.
 *
 * A property list of seven bordered inputs reads as a form to fill in; this is
 * a record to read, which happens to be editable. The affordance arrives on
 * hover and focus, where it is needed, and the resting state stays a list.
 */
const ghost =
  "border-transparent bg-transparent shadow-none hover:bg-accent focus-visible:border-ring dark:bg-transparent dark:hover:bg-accent/50"

function Row({
  icon: Icon,
  label,
  htmlFor,
  children,
}: {
  icon: LucideIcon
  label: string
  htmlFor?: string
  children: React.ReactNode
}) {
  return (
    <div className="grid grid-cols-[8rem_1fr] items-center gap-2 py-1">
      <label
        htmlFor={htmlFor}
        className="text-muted-foreground flex items-center gap-2 text-sm"
      >
        <Icon className="size-4 shrink-0" aria-hidden />
        {label}
      </label>
      <div className="min-w-0 text-sm">{children}</div>
    </div>
  )
}

/** Text that saves when you leave it, and forgets the edit on Escape. */
function EditableText({
  value,
  onCommit,
  multiline,
  className,
  placeholder,
  id,
  ariaLabel,
}: {
  value: string
  onCommit: (next: string) => void
  multiline?: boolean
  className?: string
  placeholder?: string
  id?: string
  ariaLabel?: string
}) {
  const [draft, setDraft] = useState(value)
  // The field is fed by the server after every save, and by a bot editing the
  // same task; re-sync unless the reader is the one holding the value.
  const [editing, setEditing] = useState(false)
  useEffect(() => {
    if (!editing) setDraft(value)
  }, [value, editing])

  const commit = () => {
    setEditing(false)
    if (draft !== value) onCommit(draft)
  }

  const shared = {
    id,
    "aria-label": ariaLabel,
    value: draft,
    placeholder,
    onFocus: () => setEditing(true),
    onBlur: commit,
    className: cn(ghost, className),
  }

  return multiline ? (
    <Textarea
      {...shared}
      rows={3}
      onChange={(e) => setDraft(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          setDraft(value)
          setEditing(false)
          e.currentTarget.blur()
        }
      }}
    />
  ) : (
    <Input
      {...shared}
      onChange={(e) => setDraft(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur()
        if (e.key === "Escape") {
          setDraft(value)
          setEditing(false)
          e.currentTarget.blur()
        }
      }}
    />
  )
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

/**
 * A task's fields, edited where they are read.
 *
 * There is no separate edit screen: a form that restates the record you are
 * already looking at makes you read it twice and choose between them. Each
 * field saves on its own — a select when it changes, text when you leave it —
 * so there is nothing to submit and nothing to discard.
 */
export function TaskProperties({ task }: { task: TaskPublic }) {
  const { user: currentUser } = useAuth()
  const update = useTaskUpdate(task)
  const ids = useId()

  // A subtask has no project or schedule of its own: it follows the task at
  // the top of its tree, which is the one that can be moved (FR-02.4).
  const isSubtask = Boolean(task.parent_id)

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: async () =>
      (await ProjectsService.readProjects({ query: { skip: 0, limit: 100 } }))
        .data,
    enabled: !isSubtask,
  })

  const save = (patch: TaskUpdate) => update.save(patch)

  return (
    <>
      <div className="flex items-start gap-3 px-6 pb-4">
        <span className="mt-2.5">
          <CompleteTask task={task} />
        </span>
        <EditableText
          value={task.title}
          ariaLabel="Task title"
          onCommit={(title) => title.trim() && save({ title: title.trim() })}
          className="h-auto px-2 py-1.5 text-xl leading-snug font-semibold md:text-xl"
        />
      </div>

      <div className="divide-y px-6 py-2">
        <Row icon={task.completed ? CircleCheck : CircleDashed} label="Status">
          <span className="px-2">
            {task.completed ? (
              <span className="text-primary font-medium">Completed</span>
            ) : (
              "Not completed"
            )}
          </span>
        </Row>

        <Row icon={FolderKanban} label="Project" htmlFor={`${ids}-project`}>
          {isSubtask ? (
            <span className="text-muted-foreground px-2">
              Follows its parent task
            </span>
          ) : (
            <Select
              value={task.project_id}
              onValueChange={(project_id) => save({ project_id })}
            >
              <SelectTrigger
                id={`${ids}-project`}
                className={cn(ghost, "w-full")}
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(projects?.data ?? []).map((project) => (
                  <SelectItem key={project.id} value={project.id}>
                    {project.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </Row>

        <Row icon={Calendar} label="Due date" htmlFor={`${ids}-due`}>
          <Input
            id={`${ids}-due`}
            type="date"
            value={task.due_date ?? ""}
            onChange={(e) => save({ due_date: e.target.value || null })}
            className={cn(ghost, "w-full")}
          />
        </Row>

        <Row icon={Flag} label="Priority" htmlFor={`${ids}-priority`}>
          <Select
            value={task.priority ?? NO_PRIORITY}
            onValueChange={(value) =>
              save({
                priority:
                  value === NO_PRIORITY
                    ? null
                    : (value as TaskUpdate["priority"]),
              })
            }
          >
            <SelectTrigger
              id={`${ids}-priority`}
              className={cn(ghost, "w-full")}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NO_PRIORITY}>No priority</SelectItem>
              {["P1", "P2", "P3", "P4"].map((priority) => (
                <SelectItem key={priority} value={priority}>
                  {priority}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Row>

        <Row icon={UserIcon} label="Assignee">
          <AssigneeSelect
            value={assigneeFormValue(task)}
            onChange={(value) =>
              save({ assignee_id: toAssigneeId(value, currentUser?.id) })
            }
            currentUserEmail={currentUser?.email}
            current={task.assignee_bot_user ?? undefined}
            className={ghost}
          />
        </Row>

        <Row icon={Tag} label="Tags">
          <TagsField
            value={task.tags ?? []}
            onChange={(tags) => save({ tags })}
            className={cn(ghost, "w-full")}
          />
        </Row>

        <Row icon={Repeat} label="Repeat" htmlFor={`${ids}-repeat`}>
          {isSubtask ? (
            <span className="text-muted-foreground px-2">
              Only a task at the top of its tree can repeat
            </span>
          ) : (
            <div className="flex items-center gap-2">
              <Select
                value={task.recurrence?.frequency ?? NO_RECURRENCE}
                onValueChange={(value) =>
                  save({
                    recurrence:
                      value === NO_RECURRENCE
                        ? null
                        : {
                            frequency: value as RecurrenceFrequency,
                            // A new "every N days" rule needs an interval to
                            // be a rule at all; it starts at the shortest one.
                            interval_days:
                              value === "every_n_days"
                                ? (task.recurrence?.interval_days ?? 2)
                                : null,
                          },
                  })
                }
              >
                <SelectTrigger
                  id={`${ids}-repeat`}
                  className={cn(ghost, "w-full")}
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_RECURRENCE}>Does not repeat</SelectItem>
                  <SelectItem value="daily">Every day</SelectItem>
                  <SelectItem value="weekly">Every week</SelectItem>
                  <SelectItem value="monthly">Every month</SelectItem>
                  <SelectItem value="every_n_days">Every N days</SelectItem>
                </SelectContent>
              </Select>
              {task.recurrence?.frequency === "every_n_days" && (
                <Input
                  type="number"
                  min={2}
                  aria-label="Days between repeats"
                  defaultValue={task.recurrence.interval_days ?? 2}
                  onBlur={(e) => {
                    const days = Number(e.target.value)
                    if (days >= 2 && days !== task.recurrence?.interval_days) {
                      save({
                        recurrence: {
                          frequency: "every_n_days",
                          interval_days: days,
                        },
                      })
                    }
                  }}
                  className={cn(ghost, "w-20 shrink-0")}
                />
              )}
            </div>
          )}
        </Row>

        <Row icon={Clock} label="Created">
          <span className="text-muted-foreground px-2">
            {task.created_at ? (
              <time dateTime={task.created_at}>
                {formatDateTime(task.created_at)}
              </time>
            ) : (
              "Unknown"
            )}
          </span>
        </Row>
      </div>

      <div className="border-t px-6 py-5">
        <h3 className="mb-2 px-2 text-sm font-medium">Description</h3>
        <EditableText
          multiline
          value={task.description ?? ""}
          placeholder="Add a description"
          ariaLabel="Task description"
          onCommit={(description) =>
            save({ description: description.trim() || null })
          }
        />
      </div>

      <DueDateScopeDialog
        open={update.scopeNeeded}
        onOpenChange={(open) => !open && update.cancelScope()}
        onChoose={update.chooseScope}
        pending={update.isPending}
      />
    </>
  )
}
