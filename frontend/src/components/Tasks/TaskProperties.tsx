import { useQuery } from "@tanstack/react-query"
import {
  Calendar,
  CalendarPlus,
  Flag,
  FolderKanban,
  ListTodo,
  Repeat,
  Tag,
  User as UserIcon,
} from "lucide-react"
import { useId } from "react"

import type {
  BotUserRef,
  RecurrenceFrequency,
  TaskPriority,
  TaskPublic,
  TaskStatus,
  TaskUpdate,
} from "@/client"
import { DayField } from "@/components/Common/DayField"
import {
  DescriptionSection,
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
import { projectsQuery } from "@/lib/serverState"
import { cn } from "@/lib/utils"
import { AssigneeSelect, assigneeFormValue, toAssigneeId } from "./assignee"
import type { TaskFields } from "./draft"
import {
  DueDateScopeDialog,
  IntervalDaysField,
  MIN_INTERVAL_DAYS,
  NO_RECURRENCE,
} from "./recurrence"
import { STATUS_LABELS, STATUSES, StatusGlyph, useTaskStatus } from "./status"
import { TagPicker } from "./TagPicker"
import { useTaskUpdate } from "./useTaskUpdate"

const NO_PRIORITY = "none"

/**
 * The property rows a task has from the moment it is written down: project,
 * due date, priority, assignee, tags and repeat.
 *
 * They render against a source rather than a record — the current values, and
 * a way to change some of them — so the task's panel and the draft in capture
 * are one set of rows. A record saves each change as it is made; a draft holds
 * it until the task is created. Rows only a record has go in `before` and
 * `after`.
 */
export function TaskPropertyRows({
  fields,
  onChange,
  isSubtask,
  currentBot,
  defaultProjectName,
  before,
  after,
}: {
  fields: TaskFields
  onChange: (patch: Partial<TaskFields>) => void
  /**
   * A subtask has no project or schedule of its own: it follows the task at
   * the top of its tree, which is the one that can be moved (FR-02.4).
   */
  isSubtask: boolean
  /** A deleted bot user the task keeps, offered only to keep it. */
  currentBot?: BotUserRef | null
  /** What an unset project is called: the default a draft lands in. */
  defaultProjectName?: string
  before?: React.ReactNode
  after?: React.ReactNode
}) {
  const { user: currentUser } = useAuth()
  const ids = useId()

  const { data: projects } = useQuery({
    ...projectsQuery(),
    enabled: !isSubtask,
  })
  const inbox = projects?.data.find((project) => project.is_inbox)

  return (
    <PropertyList>
      {before}

      <PropertyRow
        icon={FolderKanban}
        label="Project"
        htmlFor={`${ids}-project`}
      >
        {isSubtask ? (
          <ReadOnlyValue>Follows its parent task</ReadOnlyValue>
        ) : (
          <Select
            // An unset project is the Inbox, which is a project like any
            // other once the list of them is in.
            value={fields.project_id ?? inbox?.id ?? ""}
            onValueChange={(project_id) => onChange({ project_id })}
          >
            <SelectTrigger
              id={`${ids}-project`}
              className={cn(ghost, "w-full")}
            >
              <SelectValue placeholder={defaultProjectName} />
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
          value={fields.due_date}
          onChange={(due_date) => onChange({ due_date })}
          className={ghost}
        />
      </PropertyRow>

      <PropertyRow icon={Flag} label="Priority" htmlFor={`${ids}-priority`}>
        <Select
          value={fields.priority ?? NO_PRIORITY}
          onValueChange={(value) =>
            onChange({
              priority: value === NO_PRIORITY ? null : (value as TaskPriority),
            })
          }
        >
          <SelectTrigger id={`${ids}-priority`} className={cn(ghost, "w-full")}>
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
          value={fields.assignee}
          onChange={(assignee) => onChange({ assignee })}
          currentUserEmail={currentUser?.email}
          current={currentBot ?? undefined}
          className={ghost}
        />
      </PropertyRow>

      <PropertyRow icon={Tag} label="Tags">
        <TagPicker
          value={fields.tags}
          onChange={(tags) => onChange({ tags })}
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
              value={fields.recurrence?.frequency ?? NO_RECURRENCE}
              onValueChange={(value) =>
                onChange({
                  recurrence:
                    value === NO_RECURRENCE
                      ? null
                      : {
                          frequency: value as RecurrenceFrequency,
                          // A new "every N days" rule needs an interval to be
                          // a rule at all; it starts at the shortest one.
                          interval_days:
                            value === "every_n_days"
                              ? (fields.recurrence?.interval_days ??
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
            {fields.recurrence?.frequency === "every_n_days" && (
              <IntervalDaysField
                value={fields.recurrence.interval_days ?? MIN_INTERVAL_DAYS}
                onCommit={(interval_days) =>
                  onChange({
                    recurrence: { frequency: "every_n_days", interval_days },
                  })
                }
                className={cn(ghost, "w-20 shrink-0")}
              />
            )}
          </div>
        )}
      </PropertyRow>

      {after}
    </PropertyList>
  )
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
  // Status has its own path: moving to done may need the subtasks prompt.
  const status = useTaskStatus(task)
  const ids = useId()

  const fields: TaskFields = {
    project_id: task.project_id,
    due_date: task.due_date ?? null,
    priority: task.priority ?? null,
    assignee: assigneeFormValue(task),
    tags: task.tags ?? [],
    recurrence: task.recurrence ?? null,
  }

  const save = (patch: Partial<TaskFields>) => {
    const { assignee, ...rest } = patch
    const body: TaskUpdate = { ...rest }
    if (assignee !== undefined) {
      body.assignee_id = toAssigneeId(assignee, currentUser?.id)
    }
    update.save(body)
  }

  return (
    <>
      <TaskPropertyRows
        fields={fields}
        onChange={save}
        isSubtask={Boolean(task.parent_id)}
        currentBot={task.assignee_bot_user}
        before={
          // The row's icon is fixed like every other row's; the value carries
          // the status's own glyph.
          <PropertyRow icon={ListTodo} label="Status" htmlFor={`${ids}-status`}>
            <Select
              value={task.status}
              onValueChange={(value) => status.change(value as TaskStatus)}
              disabled={status.isPending}
            >
              <SelectTrigger
                id={`${ids}-status`}
                className={cn(ghost, "w-full")}
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STATUSES.map((value) => (
                  <SelectItem key={value} value={value}>
                    <StatusGlyph status={value} />
                    {STATUS_LABELS[value]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </PropertyRow>
        }
        after={
          <PropertyRow icon={CalendarPlus} label="Created">
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
        }
      />

      <DescriptionSection>
        <EditableText
          multiline
          value={task.description ?? ""}
          placeholder="Add a description"
          ariaLabel="Task description"
          onCommit={(description) => {
            update.save({ description: description.trim() || null })
          }}
        />
      </DescriptionSection>

      {status.prompt}

      <DueDateScopeDialog
        open={update.scopeNeeded}
        onOpenChange={(open) => !open && update.cancelScope()}
        onChoose={update.chooseScope}
        pending={update.isPending}
      />
    </>
  )
}
