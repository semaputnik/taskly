import { useQuery } from "@tanstack/react-query"
import { Bot } from "lucide-react"
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
  quiet,
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
import { PriorityOption, PriorityValue } from "./priority"
import {
  IntervalDaysField,
  MIN_INTERVAL_DAYS,
  NO_RECURRENCE,
} from "./recurrence"
import { STATUS_LABELS, STATUSES, StatusMark } from "./status"
import { TagPicker } from "./TagPicker"
import { useTaskStatus, useTaskUpdate } from "./useTaskWrites"
import { PRIORITIES } from "./writes"

const NO_PRIORITY = "none"

/** The description reads as text in the column and is a field when reached. */
export const descriptionClass =
  "-ml-2 w-[calc(100%+1rem)] resize-none px-2 py-1.5 text-[15px] leading-normal text-ink-2 md:text-[15px]"

/**
 * The due date's button, flat like the selects beside it. The picker's
 * calendar glyph stands where a select has its chevron: shown on reaching for
 * the value.
 */
const dueClass = cn(
  quiet,
  "h-[30px] justify-start pointer-coarse:h-11 md:text-[15px] [&_svg]:size-3 [&_svg]:opacity-0 hover:[&_svg]:opacity-100 focus-visible:[&_svg]:opacity-100 pointer-coarse:[&_svg]:opacity-60",
)

/**
 * The property rows a task has from the moment it is written down: project,
 * due date, priority, assignee, tags and repeat.
 *
 * They render against a source rather than a record: the current values, and
 * a way to change some of them, so the task's panel and the draft in capture
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

      <PropertyRow label="Project" htmlFor={`${ids}-project`}>
        {isSubtask ? (
          <ReadOnlyValue>Follows its parent task</ReadOnlyValue>
        ) : (
          <Select
            // An unset project is the Inbox, which is a project like any
            // other once the list of them is in.
            value={fields.project_id ?? inbox?.id ?? ""}
            onValueChange={(project_id) => onChange({ project_id })}
          >
            <SelectTrigger id={`${ids}-project`} className={quiet}>
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

      <PropertyRow label="Due" htmlFor={`${ids}-due`}>
        <DayField
          id={`${ids}-due`}
          label="Due date"
          value={fields.due_date}
          onChange={(due_date) => onChange({ due_date })}
          className={dueClass}
        />
      </PropertyRow>

      <PropertyRow label="Priority" htmlFor={`${ids}-priority`}>
        <Select
          value={fields.priority ?? NO_PRIORITY}
          onValueChange={(value) =>
            onChange({
              priority: value === NO_PRIORITY ? null : (value as TaskPriority),
            })
          }
        >
          <SelectTrigger id={`${ids}-priority`} className={quiet}>
            <SelectValue>
              <PriorityValue priority={fields.priority} />
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NO_PRIORITY}>No priority</SelectItem>
            {PRIORITIES.map((priority) => (
              <SelectItem key={priority} value={priority}>
                <PriorityOption priority={priority} />
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </PropertyRow>

      <PropertyRow label="Assignee" htmlFor={`${ids}-assignee`}>
        <AssigneeSelect
          id={`${ids}-assignee`}
          value={fields.assignee}
          onChange={(assignee) => onChange({ assignee })}
          currentUserEmail={currentUser?.email}
          current={currentBot ?? undefined}
          className={quiet}
        />
      </PropertyRow>

      <PropertyRow label="Tags">
        <TagPicker
          value={fields.tags}
          onChange={(tags) => onChange({ tags })}
        />
      </PropertyRow>

      <PropertyRow label="Repeat" htmlFor={`${ids}-repeat`}>
        {isSubtask ? (
          <ReadOnlyValue>
            Only a task at the top of its tree can repeat
          </ReadOnlyValue>
        ) : (
          <>
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
                className={cn(quiet, !fields.recurrence && "text-ink-3")}
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
                className={cn(
                  ghost,
                  "h-[30px] w-16 shrink-0 text-[15px] md:text-[15px]",
                )}
              />
            )}
          </>
        )}
      </PropertyRow>

      {after}
    </PropertyList>
  )
}

/**
 * Who filed the task, said after the moment it was filed: you, or the bot user
 * that did, named with the same glyph the assignee row gives a bot. A bot user
 * deleted since keeps its place on what it filed (FR-08.19) and says so.
 *
 * Tasks filed before the reporter was recorded name nobody at all, rather than
 * claiming an author the database never held.
 */
export function reporterName(task: TaskPublic): string | null {
  const bot = task.reporter_bot_user
  if (bot) return bot.deleted ? `${bot.name} (deleted)` : bot.name
  return task.reporter_id ? "you" : null
}

function Reporter({ task }: { task: TaskPublic }) {
  const name = reporterName(task)
  if (!name) return null
  return (
    <>
      <span aria-hidden> · </span>
      <span className="sr-only">, </span>
      by{" "}
      {task.reporter_bot_user && (
        <Bot className="mr-1 inline size-3.5 align-[-2px]" aria-hidden />
      )}
      {name}
    </>
  )
}

/**
 * A task's fields, edited where they are read.
 *
 * There is no separate edit screen: a form that restates the record you are
 * already looking at makes you read it twice and choose between them. Each
 * field saves on its own: a select when it changes, text when you leave it,
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
    void update.save(body)
  }

  return (
    <>
      <TaskPropertyRows
        fields={fields}
        onChange={save}
        isSubtask={Boolean(task.parent_id)}
        currentBot={task.assignee_bot_user}
        before={
          // The value carries the status's own mark, in the priority's colour
          // as everywhere else the mark is drawn.
          <PropertyRow label="Status" htmlFor={`${ids}-status`}>
            <Select
              value={task.status}
              onValueChange={(value) => status.change(value as TaskStatus)}
              disabled={status.isPending}
            >
              <SelectTrigger id={`${ids}-status`} className={quiet}>
                <SelectValue>
                  <StatusMark
                    status={task.status}
                    priority={task.priority}
                    className="size-4"
                  />
                  {STATUS_LABELS[task.status]}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {STATUSES.map((value) => (
                  <SelectItem key={value} value={value}>
                    <StatusMark status={value} />
                    {STATUS_LABELS[value]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </PropertyRow>
        }
        after={
          // Read only, and not because it is awkward to edit: it records when
          // and by whom the task was requested, which no later request gets
          // to revise (FR-01.29).
          <PropertyRow label="Created">
            <ReadOnlyValue>
              {task.created_at ? (
                <time dateTime={task.created_at}>
                  {formatDateTime(task.created_at)}
                </time>
              ) : (
                "Unknown"
              )}
              <Reporter task={task} />
            </ReadOnlyValue>
          </PropertyRow>
        }
      />

      <DescriptionSection>
        <EditableText
          multiline
          className={descriptionClass}
          value={task.description ?? ""}
          placeholder="Add a description"
          ariaLabel="Task description"
          onCommit={(description) =>
            update.save({ description: description.trim() || null })
          }
        />
      </DescriptionSection>

      {status.prompt}

      {update.prompt}
    </>
  )
}
