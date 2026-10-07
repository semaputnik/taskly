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

/**
 * The draft as this browser keeps it.
 *
 * A draft lives in the panel, so a reload, a dropped tab or a browser that
 * restarts would take what was written with it. It is kept in this browser's
 * own storage, never sent anywhere, and given back when the draft opens
 * again; creating the task or discarding the draft clears it. Storage may be
 * refused or missing (a private window, blocked site data), so every access
 * is guarded and a draft that cannot be kept is simply not kept.
 */
export type DraftStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">

function browserStorage(): DraftStorage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

/** One draft per place it lands: a task of its own, or a subtask of one. */
function draftKey(target: DraftTarget): string {
  return `taskly:task-draft:${target.parentId ?? "top"}`
}

export function keepDraft(
  target: DraftTarget,
  draft: TaskDraft,
  storage: DraftStorage | null = browserStorage(),
): void {
  try {
    storage?.setItem(draftKey(target), JSON.stringify(draft))
  } catch {
    // Not kept; the draft on screen is unaffected.
  }
}

export function clearKeptDraft(
  target: DraftTarget,
  storage: DraftStorage | null = browserStorage(),
): void {
  try {
    storage?.removeItem(draftKey(target))
  } catch {
    // Nothing to clear that could be reached.
  }
}

const isText = (value: unknown): value is string => typeof value === "string"
const isTextOrNull = (value: unknown): value is string | null =>
  value === null || isText(value)

/** The kept draft, or null when there is none or what is there is not one. */
export function readKeptDraft(
  target: DraftTarget,
  storage: DraftStorage | null = browserStorage(),
): TaskDraft | null {
  let raw: unknown
  try {
    const stored = storage?.getItem(draftKey(target))
    if (!stored) return null
    raw = JSON.parse(stored)
  } catch {
    return null
  }
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) {
    return null
  }
  const kept = raw as Record<string, unknown>
  const base = emptyDraft(target)

  const title = kept.title ?? base.title
  const description = kept.description ?? base.description
  const assignee = kept.assignee ?? base.assignee
  const due = kept.due_date === undefined ? base.due_date : kept.due_date
  const priority = kept.priority === undefined ? base.priority : kept.priority
  const tags = kept.tags ?? base.tags
  const recurrence =
    kept.recurrence === undefined ? base.recurrence : kept.recurrence
  const project = kept.project_id

  if (
    !isText(title) ||
    !isText(description) ||
    !isText(assignee) ||
    !isTextOrNull(due) ||
    !isTextOrNull(priority) ||
    !Array.isArray(tags) ||
    !tags.every(isText) ||
    !(project === undefined || isText(project)) ||
    !(
      recurrence === null ||
      (typeof recurrence === "object" &&
        !Array.isArray(recurrence) &&
        isText((recurrence as Record<string, unknown>).frequency))
    )
  ) {
    return null
  }
  return {
    title,
    description,
    assignee,
    due_date: due,
    priority: priority as TaskPriority | null,
    tags,
    recurrence: recurrence as Recurrence | null,
    project_id: project ?? base.project_id,
  }
}
