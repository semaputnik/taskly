import {
  type DueDateScope,
  type SubtaskCompletion,
  type TaskBulkUpdate,
  type TaskCreate,
  type TaskPublic,
  type TaskStatus,
  TasksService,
  type TaskUpdate,
} from "@/client"
import { TaskPrioritySchema } from "@/client/schemas.gen"
import {
  type BatchRefusal,
  batchRefusals,
  Refusal,
  refusalCode,
} from "@/lib/apiErrors"
import type { Change } from "@/lib/serverState"
import { sameRecurrence } from "./recurrence"

/**
 * Task writes: every change, creation and deletion of tasks, and what came
 * of it.
 *
 * Each write resolves to one outcome — saved, or refused and why — and
 * reports the change it made to the server state whatever the outcome, so
 * the screen catches up with what the server holds. The rules a write has to
 * get right before it is sent live here too: moving an open occurrence's due
 * date asks how far the move reaches (FR-01.17), and a batch cannot move one.
 *
 * Plain functions over the generated client; the hooks in `useTaskWrites`
 * add the feedback and the prompts.
 */

/** The priorities a task can have, highest first. */
export const PRIORITIES = TaskPrioritySchema.enum

/** Why a write did not land. */
export type Refused =
  /** Moving to done needs a decision about the task's open subtasks. */
  | { reason: "open subtasks" }
  /** Deleting would take subtasks with it, which has to be confirmed. */
  | { reason: "has subtasks" }
  /** A moved due date on a recurring task needs a scope; nothing was sent. */
  | { reason: "needs scope" }
  /** A batch could not be done whole: these tasks stood in the way. */
  | { reason: "batch"; refusals: BatchRefusal[] }
  /** Anything else, to be said as the API said it. */
  | { reason: "failed"; error: unknown }

export type Outcome<T = unknown> =
  | { saved: true; data: T }
  | ({ saved: false } & Refused)

/** Where a write reports what it changed. */
export type Report = (change: Change) => unknown

function refusedFor(error: unknown): Refused {
  switch (refusalCode(error)) {
    case Refusal.OPEN_SUBTASKS:
      return { reason: "open subtasks" }
    case Refusal.HAS_SUBTASKS:
      return { reason: "has subtasks" }
    case Refusal.BULK_REFUSED:
      return { reason: "batch", refusals: batchRefusals(error) ?? [] }
    default:
      return { reason: "failed", error }
  }
}

async function attempt<T>(
  report: Report,
  change: Change,
  send: () => Promise<{ data: T }>,
): Promise<Outcome<T>> {
  try {
    const { data } = await send()
    return { saved: true, data }
  } catch (error) {
    return { saved: false, ...refusedFor(error) }
  } finally {
    report(change)
  }
}

const isRecurring = (task: TaskPublic) => Boolean(task.recurrence)

/**
 * Whether saving `body` moves the due date of an open occurrence on its own,
 * which means something different for the rest of the series depending on
 * the scope. A changed rule restarts the schedule anyway.
 */
export function asksForScope(task: TaskPublic, body: TaskUpdate): boolean {
  return Boolean(
    isRecurring(task) &&
      task.status !== "done" &&
      body.due_date !== undefined &&
      body.due_date !== (task.due_date ?? null) &&
      sameRecurrence(body.recurrence ?? task.recurrence, task.recurrence),
  )
}

/**
 * Save fields of a task. A moved due date on an open occurrence is not sent
 * until `scope` says how far it reaches.
 */
export async function updateTask(
  report: Report,
  task: TaskPublic,
  body: TaskUpdate,
  scope?: DueDateScope,
): Promise<Outcome<TaskPublic>> {
  if (!scope && asksForScope(task, body)) {
    return { saved: false, reason: "needs scope" }
  }
  return attempt(report, { type: "task changed", taskId: task.id }, () =>
    TasksService.updateTask({
      path: { task_id: task.id },
      body: scope ? { ...body, due_date_scope: scope } : body,
    }),
  )
}

/** Move a task to a status, saying what happens to open subtasks if asked. */
export function setStatus(
  report: Report,
  task: TaskPublic,
  status: TaskStatus,
  subtasks?: SubtaskCompletion,
): Promise<Outcome<TaskPublic>> {
  return attempt(report, { type: "task changed", taskId: task.id }, () =>
    TasksService.updateTask({
      path: { task_id: task.id },
      body: { status, subtasks },
    }),
  )
}

export function createTask(
  report: Report,
  body: TaskCreate,
): Promise<Outcome<TaskPublic>> {
  return attempt(report, { type: "task created" }, () =>
    TasksService.createTask({ body }),
  )
}

/** Delete a task; `withSubtasks` confirms the cascade. */
export function deleteTask(
  report: Report,
  task: TaskPublic,
  withSubtasks: boolean,
): Promise<Outcome> {
  return attempt(report, { type: "task deleted", taskId: task.id }, () =>
    TasksService.deleteTask({
      path: { task_id: task.id },
      query: { delete_subtasks: withSubtasks },
    }),
  )
}

/**
 * The tasks of a selection a batch cannot move the due date of: moving one
 * occurrence of a series asks how far the move reaches, which is a question
 * for the task's own panel. The server refuses them too; saying so here
 * spares the reader a request that could only fail.
 */
export function repeatingRefusals(tasks: TaskPublic[]): BatchRefusal[] {
  return tasks.filter(isRecurring).map((task) => ({
    task_id: task.id,
    code: Refusal.TASK_REPEATS,
    message: `“${task.title}” repeats. Move its due date from the task itself, where the rest of the series can be settled.`,
  }))
}

/**
 * Apply one set of changes to a selection. `known` are the selected tasks
 * this screen has seen, which is what is checked before sending.
 */
export async function bulkUpdate(
  report: Report,
  taskIds: string[],
  known: TaskPublic[],
  body: Omit<TaskBulkUpdate, "task_ids">,
): Promise<Outcome<{ updated?: number }>> {
  if ("due_date" in body) {
    const refusals = repeatingRefusals(
      known.filter((task) => taskIds.includes(task.id)),
    )
    if (refusals.length > 0) {
      return { saved: false, reason: "batch", refusals }
    }
  }
  return attempt(report, { type: "tasks changed in bulk" }, () =>
    TasksService.bulkUpdateTasks({ body: { ...body, task_ids: taskIds } }),
  )
}

/** Delete a selection, and its subtasks with it, as one event. */
export function bulkDelete(
  report: Report,
  taskIds: string[],
): Promise<Outcome<{ deleted?: number }>> {
  return attempt(report, { type: "tasks changed in bulk" }, () =>
    TasksService.bulkDeleteTasks({
      body: { task_ids: taskIds, delete_subtasks: true },
    }),
  )
}
