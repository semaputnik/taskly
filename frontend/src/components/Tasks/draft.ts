import type { Recurrence, TaskCreate, TaskPriority } from "../../client"

/**
 * A task before it exists: what capture holds while the reader fills it in.
 *
 * Plain data and plain functions, so the rules of a draft — what it sends,
 * what carries over to the next one, and when closing it would lose work —
 * can be read and tested apart from the panel that shows it.
 */

// The assignee as the property row holds it: nobody, the user, or a bot
// user's own id.
export const UNASSIGNED = "unassigned"
export const ASSIGNED_TO_ME = "me"

/** The `assignee_id` the API takes for an assignee as the row holds it. */
export function toAssigneeId(
  value: string | undefined,
  currentUserId: string | undefined,
): string | null {
  if (!value || value === UNASSIGNED) return null
  return value === ASSIGNED_TO_ME ? (currentUserId ?? null) : value
}

/** The properties a task has from creation, as the property rows edit them. */
export interface TaskFields {
  /** Undefined is the default project: the Inbox, unless a list says else. */
  project_id?: string
  due_date: string | null
  priority: TaskPriority | null
  assignee: string
  tags: string[]
  recurrence: Recurrence | null
}

export interface TaskDraft extends TaskFields {
  title: string
  description: string
}

/** Where a draft lands, which decides what it may carry. */
export interface DraftTarget {
  projectId?: string
  parentId?: string
}

export function emptyDraft(target: DraftTarget): TaskDraft {
  return {
    title: "",
    description: "",
    project_id: target.projectId,
    due_date: null,
    priority: null,
    assignee: UNASSIGNED,
    tags: [],
    recurrence: null,
  }
}

/**
 * The one create request a draft becomes. A subtask follows its parent's
 * project and cannot repeat, so it sends neither (FR-02.4).
 */
export function draftToCreate(
  draft: TaskDraft,
  target: DraftTarget,
  currentUserId: string | undefined,
): TaskCreate {
  const description = draft.description.trim()
  const body: TaskCreate = {
    title: draft.title.trim(),
    description: description || null,
    due_date: draft.due_date,
    priority: draft.priority,
    assignee_id: toAssigneeId(draft.assignee, currentUserId),
    tags: draft.tags,
  }
  if (target.parentId) return { ...body, parent_id: target.parentId }
  return {
    ...body,
    project_id: draft.project_id,
    recurrence: draft.recurrence,
  }
}

/**
 * The next draft after a capture that keeps going: the words are the task's
 * own and go, the properties are the run's and stay, so a run of tasks
 * sharing a day, a priority or a tag costs one setting.
 */
export function carryOver(draft: TaskDraft): TaskDraft {
  return { ...draft, title: "", description: "" }
}

/**
 * Whether closing the draft would lose something the reader put there: a
 * title, a description, or any property moved off the draft's defaults —
 * which, after a run of captures, are the values carried over.
 */
export function isTouched(draft: TaskDraft, defaults: TaskDraft): boolean {
  if (draft.title !== "" || draft.description !== "") return true
  return (
    draft.project_id !== defaults.project_id ||
    draft.due_date !== defaults.due_date ||
    draft.priority !== defaults.priority ||
    draft.assignee !== defaults.assignee ||
    !sameList(draft.tags, defaults.tags) ||
    !sameRule(draft.recurrence, defaults.recurrence)
  )
}

function sameList(a: readonly string[], b: readonly string[]): boolean {
  return a.length === b.length && a.every((item, index) => item === b[index])
}

function sameRule(a: Recurrence | null, b: Recurrence | null): boolean {
  if (a === null || b === null) return a === b
  return (
    a.frequency === b.frequency &&
    (a.interval_days ?? null) === (b.interval_days ?? null)
  )
}
