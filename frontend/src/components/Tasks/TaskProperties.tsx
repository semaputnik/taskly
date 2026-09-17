import { useQuery } from "@tanstack/react-query"
import {
  Calendar,
  CircleCheck,
  CircleDashed,
  Clock,
  Flag,
  FolderKanban,
  Repeat,
  Tag,
  User as UserIcon,
} from "lucide-react"
import { useId } from "react"

import {
  ProjectsService,
  type RecurrenceFrequency,
  type TaskPublic,
  type TaskUpdate,
} from "@/client"
import { DayField } from "@/components/Common/DayField"
import {
  EditableText,
  ghost,
  PropertyList,
  PropertyRow,
  ReadOnlyValue,
} from "@/components/Records/RecordPanel"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useAuth from "@/hooks/useAuth"
import { formatDateTime } from "@/lib/dates"
import { cn } from "@/lib/utils"
import { AssigneeSelect, assigneeFormValue, toAssigneeId } from "./assignee"
import {
  DueDateScopeDialog,
  IntervalDaysField,
  MIN_INTERVAL_DAYS,
  NO_RECURRENCE,
} from "./recurrence"
import { TagsField } from "./TagsField"
import { useTaskUpdate } from "./useTaskUpdate"

const NO_PRIORITY = "none"

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
      <PropertyList>
        <PropertyRow
          icon={task.status === "done" ? CircleCheck : CircleDashed}
          label="Status"
        >
          <span className="px-2">
            {task.status === "done" ? (
              <span className="font-medium">Completed</span>
            ) : (
              "Not completed"
            )}
          </span>
        </PropertyRow>

        <PropertyRow
          icon={FolderKanban}
          label="Project"
          htmlFor={`${ids}-project`}
        >
          {isSubtask ? (
            <ReadOnlyValue>Follows its parent task</ReadOnlyValue>
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
        </PropertyRow>

        <PropertyRow icon={Calendar} label="Due date" htmlFor={`${ids}-due`}>
          <DayField
            id={`${ids}-due`}
            label="Due date"
            value={task.due_date}
            onChange={(due_date) => save({ due_date })}
            className={ghost}
          />
        </PropertyRow>

        <PropertyRow icon={Flag} label="Priority" htmlFor={`${ids}-priority`}>
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
        </PropertyRow>

        <PropertyRow icon={UserIcon} label="Assignee">
          <AssigneeSelect
            value={assigneeFormValue(task)}
            onChange={(value) =>
              save({ assignee_id: toAssigneeId(value, currentUser?.id) })
            }
            currentUserEmail={currentUser?.email}
            current={task.assignee_bot_user ?? undefined}
            className={ghost}
          />
        </PropertyRow>

        <PropertyRow icon={Tag} label="Tags" htmlFor={`${ids}-tags`}>
          <TagsField
            id={`${ids}-tags`}
            value={task.tags ?? []}
            onChange={(tags) => save({ tags })}
            className={cn(ghost, "w-full")}
          />
        </PropertyRow>

        <PropertyRow icon={Repeat} label="Repeat" htmlFor={`${ids}-repeat`}>
          {isSubtask ? (
            <ReadOnlyValue>
              Only a task at the top of its tree can repeat
            </ReadOnlyValue>
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
                                ? (task.recurrence?.interval_days ??
                                  MIN_INTERVAL_DAYS)
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
                <IntervalDaysField
                  value={task.recurrence.interval_days ?? MIN_INTERVAL_DAYS}
                  onCommit={(interval_days) =>
                    save({
                      recurrence: { frequency: "every_n_days", interval_days },
                    })
                  }
                  className={cn(ghost, "w-20 shrink-0")}
                />
              )}
            </div>
          )}
        </PropertyRow>

        <PropertyRow icon={Clock} label="Created">
          <ReadOnlyValue>
            {task.created_at ? (
              <time dateTime={task.created_at}>
                {formatDateTime(task.created_at)}
              </time>
            ) : (
              "Unknown"
            )}
          </ReadOnlyValue>
        </PropertyRow>
      </PropertyList>

      <div className="border-t px-6 py-5">
        <h3 className="mb-2 px-2 text-sm font-medium">Description</h3>
        <EditableText
          multiline
          value={task.description ?? ""}
          placeholder="Add a description"
          ariaLabel="Task description"
          onCommit={(description) => {
            save({ description: description.trim() || null })
          }}
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
