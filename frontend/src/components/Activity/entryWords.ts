import type { ActivityEntryPublic, TaskStatus } from "@/client"
import { STATUS_LABELS } from "@/components/Tasks/statuses"
import { formatDayPlain } from "@/lib/dates"

/**
 * Who speaks the sentence. The log page names its subject — "Created the
 * task Ship it" — because the reader is not necessarily looking at the
 * thing it names. The task panel is already open on the task, so it leaves
 * the subject out and lets the verb carry it implicitly: "created this",
 * "moved it to Done".
 */
export type Voice = "names-its-subject" | "subject-implicit"

/**
 * One entry's sentence, in parts: everything that reads before the subject
 * (or, when the entry names no single record — a batch names the
 * selection, not a task — the whole sentence), whether there is a subject
 * slot at all, and whatever reads after it.
 *
 * `subject-implicit` never asks for a slot: whatever stands in for the
 * subject ("it", "this") is already folded into `verb`, so `subject` is
 * always `false` and `after` always `""` in that voice. The caller renders
 * the slot itself — a link for the log page, struck through when the
 * record is gone; nothing at all for the task panel.
 */
export interface EntryWords {
  verb: string
  subject: boolean
  after: string
}

function detail<T>(entry: ActivityEntryPublic, key: string): T | undefined {
  return entry.details[key] as T | undefined
}

/** "1 task" or "3 tasks": the count a reader needs for either voice. */
function pluralize(n: number, singular: string, plural = `${singular}s`): string {
  return n === 1 ? `1 ${singular}` : `${n} ${plural}`
}

/** "task" or "tasks" on its own, for a phrase that already carries the count. */
function plural(n: number, singular: string, pluralForm = `${singular}s`): string {
  return n === 1 ? singular : pluralForm
}

interface ProjectRef {
  id: string
  name: string | null
}

function projectName(project: ProjectRef | null | undefined): string {
  return project?.name ?? "a project that no longer exists"
}

// What each field is called when an entry lists what changed, in the voice
// that names its subject.
const FIELD_LABELS: Record<string, string> = {
  title: "title",
  description: "description",
  due_date: "due date",
  priority: "priority",
  tags: "tags",
  recurrence: "repeat",
}

/** What a batch did, in the words the reader will recognise. */
function describeBatch(changes: Record<string, unknown>): string {
  const said: string[] = []
  // Batches from before statuses recorded `completed`.
  if ("completed" in changes) {
    said.push(changes.completed ? "completed" : "reopened")
  }
  if ("status" in changes) {
    const status = changes.status as TaskStatus
    said.push(
      status === "done" ? "completed" : `moved to ${STATUS_LABELS[status]}`,
    )
  }
  if ("priority" in changes) {
    said.push(
      changes.priority ? `priority ${changes.priority}` : "priority cleared",
    )
  }
  if ("due_date" in changes) {
    said.push(
      changes.due_date
        ? `due ${formatDayPlain(changes.due_date as string)}`
        : "due date cleared",
    )
  }
  const project = changes.project as { name?: string } | undefined
  if (project?.name) said.push(`moved to ${project.name}`)
  const added = changes.added_tags as string[] | undefined
  if (added?.length) said.push(`tagged ${added.join(", ")}`)
  const removed = changes.removed_tags as string[] | undefined
  if (removed?.length) said.push(`untagged ${removed.join(", ")}`)
  return said.join(", ")
}

// Entries from before bot users could be assigned carry only the id.
interface AssigneeRef {
  type: "user" | "bot_user"
  id: string
  name?: string
}

/**
 * Who a task was assigned to, in the voice that names its subject. A bot
 * user is named as it was called at the time, which still reads after it is
 * renamed or deleted.
 */
function namesAssignee(
  assignee: AssigneeRef | null | undefined,
  assigneeId: string | undefined,
  currentUserId: string | undefined,
): string {
  if (assignee?.type === "bot_user") {
    return `the bot user ${assignee.name}`
  }
  return (assignee?.id ?? assigneeId) === currentUserId ? "you" : "someone"
}

type Change = { from: unknown; to: unknown }

/** What a batch of field changes says, in the voice that drops its subject. */
function changedFields(changes: Record<string, Change>): string | null {
  const said: string[] = []
  if (changes.title) said.push(`renamed it to “${changes.title.to}”`)
  if (changes.description) said.push("edited the description")
  if (changes.due_date) {
    said.push(
      changes.due_date.to
        ? `set the due date to ${formatDayPlain(changes.due_date.to as string)}`
        : "cleared the due date",
    )
  }
  if (changes.priority) {
    said.push(
      changes.priority.to
        ? `set the priority to ${changes.priority.to}`
        : "cleared the priority",
    )
  }
  if (changes.tags) said.push(changedTags(changes.tags))
  if (changes.recurrence) {
    said.push(
      changes.recurrence.to ? "changed how it repeats" : "stopped it repeating",
    )
  }
  return said.length ? joined(said) : null
}

function changedTags({ from, to }: Change): string {
  const before = (from as string[] | null) ?? []
  const after = (to as string[] | null) ?? []
  const added = after.filter((tag) => !before.includes(tag))
  const removed = before.filter((tag) => !after.includes(tag))
  const said = [
    added.length ? `tagged it ${added.join(", ")}` : null,
    removed.length ? `untagged ${removed.join(", ")}` : null,
  ].filter(Boolean)
  return said.length ? said.join(" and ") : "changed the tags"
}

function joined(parts: string[]): string {
  if (parts.length < 2) return parts[0]
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`
}

/** A sentence with nothing after the verb and no subject of its own. */
function whole(verb: string): EntryWords {
  return { verb, subject: false, after: "" }
}

/** A sentence whose subject the caller fills in. */
function withSubject(verb: string, after = ""): EntryWords {
  return { verb, subject: true, after }
}

/**
 * The 24 kinds of activity entry, each as a sentence's parts, in a voice.
 *
 * It is built from what the entry recorded at the time, so it reads the
 * same after the task, project or tag is renamed, moved or deleted — only
 * the caller's subject slot depends on the record still being there.
 *
 * The two voices are not the same sentence twice over: `subject-implicit`
 * is addressed to a reader who already has the record open (the task
 * panel), so it says less, and sometimes says nothing at all — a comment,
 * a project or a tag is not among the actions it speaks, so this returns
 * `null` for those. `names-its-subject` speaks every action, because the
 * log page is the one place every kind of entry is read.
 */
export function entryWords(
  entry: ActivityEntryPublic,
  voice: "names-its-subject",
  currentUserId?: string,
): EntryWords
export function entryWords(
  entry: ActivityEntryPublic,
  voice: "subject-implicit",
): EntryWords | null
export function entryWords(
  entry: ActivityEntryPublic,
  voice: Voice,
  currentUserId?: string,
): EntryWords | null {
  const implicit = voice === "subject-implicit"

  switch (entry.action) {
    case "task_created": {
      const snapshot = detail<{ project: ProjectRef | null }>(entry, "task")
      if (implicit) {
        // Unlike the other voice, this only mentions the project when it
        // has a name — a project reference with none reads as if there
        // were no project at all, rather than naming it "no longer exists".
        return whole(
          snapshot?.project?.name
            ? `created this in ${snapshot.project.name}`
            : "created this",
        )
      }
      return withSubject(
        "Created",
        snapshot?.project ? ` in ${projectName(snapshot.project)}` : "",
      )
    }
    case "task_changed": {
      if (implicit) {
        const changes =
          detail<Record<string, Change>>(entry, "changes") ?? {}
        const said = changedFields(changes)
        return said ? whole(said) : null
      }
      const changes = detail<Record<string, unknown>>(entry, "changes") ?? {}
      const fields = Object.keys(changes).map((key) => FIELD_LABELS[key] ?? key)
      return withSubject(`Changed the ${fields.join(", ")} of`)
    }
    case "task_completed":
      return implicit ? whole("completed it") : withSubject("Completed")
    case "task_reopened":
      return implicit ? whole("reopened it") : withSubject("Reopened")
    case "task_status_changed": {
      const to = detail<TaskStatus>(entry, "to")
      if (implicit) {
        return whole(to ? `moved it to ${STATUS_LABELS[to]}` : "moved it")
      }
      return withSubject("Moved", ` to ${to ? STATUS_LABELS[to] : "another status"}`)
    }
    case "task_deleted": {
      if (implicit) return whole("deleted it")
      // A batch names no single task: what it deleted is the selection, and
      // the count is what the entry has to say.
      const batch = detail<number>(entry, "task_count")
      if (batch !== undefined) return whole(`Deleted ${pluralize(batch, "task")}`)
      const subtasks = detail<number>(entry, "subtask_count") ?? 0
      return withSubject(
        "Deleted",
        subtasks > 0 ? ` and ${pluralize(subtasks, "subtask")}` : "",
      )
    }
    case "task_restored": {
      if (implicit) return whole("restored it")
      const subtasks = detail<number>(entry, "subtask_count") ?? 0
      return withSubject(
        "Restored",
        subtasks > 0 ? ` and ${pluralize(subtasks, "subtask")}` : "",
      )
    }
    case "task_moved": {
      if (implicit) {
        // Only the destination, not the origin: the task panel already knows
        // where the task was, because it is reading its history in order.
        const to = detail<{ name?: string }>(entry, "to_project")
        return whole(
          to?.name ? `moved it to ${to.name}` : "moved it to another project",
        )
      }
      return withSubject(
        "Moved",
        ` from ${projectName(detail<ProjectRef>(entry, "from_project"))} to ${projectName(
          detail<ProjectRef>(entry, "to_project"),
        )}`,
      )
    }
    case "task_assigned": {
      const assignee = detail<AssigneeRef>(entry, "assignee")
      if (implicit) {
        // The only human a task can be assigned to is its owner: when they
        // did it themselves it is "yourself", when a bot user did it, "you".
        const who =
          assignee?.type === "bot_user"
            ? assignee.name ?? "a bot user"
            : entry.actor_bot_user_id
              ? "you"
              : "yourself"
        return whole(`assigned it to ${who}`)
      }
      return withSubject(
        "Assigned",
        ` to ${namesAssignee(assignee, detail<string>(entry, "assignee_id"), currentUserId)}`,
      )
    }
    case "task_unassigned": {
      if (implicit) return whole("removed the assignee")
      const previous = detail<AssigneeRef>(entry, "previous_assignee")
      if (previous?.type === "bot_user") {
        return withSubject(
          `Removed ${namesAssignee(previous, previous.id, currentUserId)} from`,
        )
      }
      return withSubject("Removed the assignee from")
    }
    case "tasks_bulk_changed": {
      const count = detail<number>(entry, "task_count") ?? 0
      if (implicit) {
        // The current task is one of the count; what matters here is how
        // many others went with it.
        const others = count - 1
        return whole(
          others > 0
            ? `changed it along with ${others} other ${plural(others, "task")}`
            : "changed it",
        )
      }
      const changes = detail<Record<string, unknown>>(entry, "changes") ?? {}
      const batch = describeBatch(changes)
      return whole(`Changed ${pluralize(count, "task")}${batch ? `: ${batch}` : ""}`)
    }
    case "attachment_added": {
      const filename = detail<string>(entry, "filename")
      return implicit
        ? whole(`attached “${filename}”`)
        : withSubject(`Attached “${filename}” to`)
    }
    case "attachment_deleted": {
      const filename = detail<string>(entry, "filename")
      return implicit
        ? whole(`removed “${filename}”`)
        : withSubject(`Removed “${filename}” from`)
    }
    // A comment is shown as the comment itself, with its author and body,
    // not as a line saying someone wrote one — so the task panel's voice
    // has nothing to say about these.
    case "comment_added":
      return implicit ? null : withSubject("Commented on")
    case "comment_edited":
      return implicit ? null : withSubject("Edited a comment on")
    case "comment_deleted":
      return implicit ? null : withSubject("Deleted a comment on")
    // Projects and tags never appear in a task's own history, so the task
    // panel's voice has nothing to say about these either.
    case "project_created":
      return implicit ? null : withSubject("Created the project")
    case "project_changed": {
      if (implicit) return null
      const changes = detail<Record<string, unknown>>(entry, "changes") ?? {}
      return withSubject(`Changed the ${Object.keys(changes).join(", ")} of the project`)
    }
    case "project_deleted": {
      if (implicit) return null
      const tasks = detail<number>(entry, "task_count") ?? 0
      return withSubject(
        "Deleted the project",
        tasks > 0 ? ` and ${pluralize(tasks, "task")}` : "",
      )
    }
    case "project_restored": {
      if (implicit) return null
      const tasks = detail<number>(entry, "task_count") ?? 0
      return withSubject(
        "Restored the project",
        tasks > 0 ? ` and ${pluralize(tasks, "task")}` : "",
      )
    }
    case "tag_created":
      return implicit ? null : withSubject("Created the tag")
    case "tag_renamed": {
      if (implicit) return null
      const change = detail<{ name?: { from: string } }>(entry, "changes")
      return withSubject(`Renamed the tag “${change?.name?.from}” to`)
    }
    case "tag_merged": {
      if (implicit) return null
      const sources = detail<string[]>(entry, "sources") ?? []
      const tasks = detail<number>(entry, "task_count") ?? 0
      return withSubject(
        `Merged ${sources.map((name) => `“${name}”`).join(", ")} into`,
        tasks > 0 ? `, moving ${pluralize(tasks, "task")} onto it` : "",
      )
    }
    case "tag_deleted": {
      if (implicit) return null
      const tasks = detail<number>(entry, "task_count") ?? 0
      return withSubject(
        "Deleted the tag",
        tasks > 0 ? `, taking it off ${pluralize(tasks, "task")}` : "",
      )
    }
  }
}

/**
 * What one log entry says about a task, as the rest of a sentence whose
 * subject is whoever made the change: "moved it to In progress", "set the
 * due date to 7 Oct". The task panel shows its history as a chronology of
 * these, so every line leaves the task out: it is the one the panel is open
 * on.
 *
 * Everything the log records about a task that the `subject-implicit` voice
 * does not know how to say returns `null`, rather than a line that reads
 * wrongly.
 */
export function describeTaskEvent(entry: ActivityEntryPublic): string | null {
  const words = entryWords(entry, "subject-implicit")
  return words ? `${words.verb}${words.after}` : null
}
