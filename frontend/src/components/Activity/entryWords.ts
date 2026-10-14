import type {
  ActivityEntryPublic,
  AssigneeRef,
  FieldChange,
  ProjectRef,
  TaskStatus,
} from "@/client"
import { nameList, plural } from "@/components/Common/words"
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

/** What a batch of field changes says, in the voice that drops its subject. */
function changedFields(changes: Record<string, FieldChange>): string | null {
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
  return said.length ? nameList(said) : null
}

function changedTags({ from, to }: FieldChange): string {
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
 * Switches on `entry.details.kind` rather than `entry.action`: the two
 * agree everywhere but one, `task_deleted`/`task_restored`, which each write
 * one of two shapes under the same action — a single task's own deletion
 * carrying its title, or a batch's, carrying only a count (ADR-0011's
 * all-or-nothing batch, declared rather than read off which fields happen
 * to be there) — so `kind` splits them into their own cases
 * (`task_deleted`/`task_deleted_batch`, `task_restored`/
 * `task_restored_batch`) the same way the generated client's own
 * discriminated union does (#299's spike). Switching on `action` instead
 * would read the same at runtime, but would not narrow `entry.details` to
 * the fields each case actually has — this way, a field this switch reads
 * is one the compiler has already checked is there.
 *
 * The two voices are not the same sentence twice over: `subject-implicit`
 * is addressed to a reader who already has the record open (the task
 * panel), so it says less, and sometimes says nothing at all — a comment,
 * a project or a tag is not among the actions it speaks, so this returns
 * `null` for those. `names-its-subject` speaks every action, because the
 * log page is the one place every kind of entry is read — a caller in that
 * voice should never actually see `null`, but the return type stays
 * nullable for both, so a 25th action with no case yet fails safely rather
 * than throwing.
 */
export function entryWords(
  entry: ActivityEntryPublic,
  voice: Voice,
  currentUserId?: string,
): EntryWords | null {
  const implicit = voice === "subject-implicit"
  const { details } = entry

  switch (details.kind) {
    case "task_created": {
      const { task } = details
      if (implicit) {
        // Unlike the other voice, this only mentions the project when it
        // has a name — a project reference with none reads as if there
        // were no project at all, rather than naming it "no longer exists".
        return whole(
          task.project?.name
            ? `created this in ${task.project.name}`
            : "created this",
        )
      }
      return withSubject(
        "Created",
        task.project ? ` in ${projectName(task.project)}` : "",
      )
    }
    case "task_changed": {
      if (implicit) {
        const said = changedFields(details.changes)
        return said ? whole(said) : null
      }
      const fields = Object.keys(details.changes).map(
        (key) => FIELD_LABELS[key] ?? key,
      )
      return withSubject(`Changed the ${fields.join(", ")} of`)
    }
    case "task_completed":
      return implicit ? whole("completed it") : withSubject("Completed")
    case "task_reopened":
      return implicit ? whole("reopened it") : withSubject("Reopened")
    case "task_status_changed": {
      const { to } = details
      if (implicit) {
        return whole(to ? `moved it to ${STATUS_LABELS[to]}` : "moved it")
      }
      return withSubject(
        "Moved",
        ` to ${to ? STATUS_LABELS[to] : "another status"}`,
      )
    }
    case "task_deleted": {
      if (implicit) return whole("deleted it")
      const subtasks = details.subtask_count ?? 0
      return withSubject(
        "Deleted",
        subtasks > 0 ? ` and ${plural(subtasks, "subtask")}` : "",
      )
    }
    case "task_deleted_batch":
      // A batch names no single task: what it deleted is the selection, and
      // the count is what the entry has to say.
      return implicit
        ? whole("deleted it")
        : whole(`Deleted ${plural(details.task_count, "task")}`)
    case "task_restored": {
      if (implicit) return whole("restored it")
      const subtasks = details.subtask_count ?? 0
      return withSubject(
        "Restored",
        subtasks > 0 ? ` and ${plural(subtasks, "subtask")}` : "",
      )
    }
    case "task_restored_batch":
      return implicit
        ? whole("restored it")
        : whole(`Restored ${plural(details.task_count, "task")}`)
    case "task_moved": {
      if (implicit) {
        // Only the destination, not the origin: the task panel already knows
        // where the task was, because it is reading its history in order.
        const to = details.to_project
        return whole(
          to?.name ? `moved it to ${to.name}` : "moved it to another project",
        )
      }
      return withSubject(
        "Moved",
        ` from ${projectName(details.from_project)} to ${projectName(
          details.to_project,
        )}`,
      )
    }
    case "task_assigned": {
      const { assignee } = details
      if (implicit) {
        // The only human a task can be assigned to is its owner: when they
        // did it themselves it is "yourself", when a bot user did it, "you".
        const who =
          assignee?.type === "bot_user"
            ? (assignee.name ?? "a bot user")
            : entry.actor_bot_user_id
              ? "you"
              : "yourself"
        return whole(`assigned it to ${who}`)
      }
      return withSubject(
        "Assigned",
        ` to ${namesAssignee(assignee, details.assignee_id ?? undefined, currentUserId)}`,
      )
    }
    case "task_unassigned": {
      // Unlike the other voice, this never names who was removed, bot user
      // or not — "removed the assignee" covers every case.
      if (implicit) return whole("removed the assignee")
      const previous = details.previous_assignee
      if (previous?.type === "bot_user") {
        return withSubject(
          `Removed ${namesAssignee(previous, previous.id, currentUserId)} from`,
        )
      }
      return withSubject("Removed the assignee from")
    }
    case "tasks_bulk_changed": {
      const { task_count: count } = details
      if (implicit) {
        // The current task is one of the count; what matters here is how
        // many others went with it.
        const others = count - 1
        return whole(
          others > 0
            ? `changed it along with ${others} other ${others === 1 ? "task" : "tasks"}`
            : "changed it",
        )
      }
      const batch = describeBatch(details.changes)
      return whole(
        `Changed ${plural(count, "task")}${batch ? `: ${batch}` : ""}`,
      )
    }
    case "attachment_added": {
      const { filename } = details
      return implicit
        ? whole(`attached “${filename}”`)
        : withSubject(`Attached “${filename}” to`)
    }
    case "attachment_deleted": {
      const { filename } = details
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
      return withSubject(
        `Changed the ${Object.keys(details.changes).join(", ")} of the project`,
      )
    }
    case "project_deleted": {
      if (implicit) return null
      const tasks = details.task_count
      return withSubject(
        "Deleted the project",
        tasks > 0 ? ` and ${plural(tasks, "task")}` : "",
      )
    }
    case "project_restored": {
      if (implicit) return null
      const tasks = details.task_count
      return withSubject(
        "Restored the project",
        tasks > 0 ? ` and ${plural(tasks, "task")}` : "",
      )
    }
    case "tag_created":
      return implicit ? null : withSubject("Created the tag")
    case "tag_renamed": {
      if (implicit) return null
      return withSubject(`Renamed the tag “${details.changes.name?.from}” to`)
    }
    case "tag_merged": {
      if (implicit) return null
      const { sources, task_count: tasks } = details
      return withSubject(
        `Merged ${sources.map((name) => `“${name}”`).join(", ")} into`,
        tasks > 0 ? `, moving ${plural(tasks, "task")} onto it` : "",
      )
    }
    case "tag_deleted": {
      if (implicit) return null
      const tasks = details.task_count
      return withSubject(
        "Deleted the tag",
        tasks > 0 ? `, taking it off ${plural(tasks, "task")}` : "",
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
