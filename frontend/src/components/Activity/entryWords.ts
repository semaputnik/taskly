import type {
  ActivityEntryPublic,
  AssigneeRef,
  FieldChange,
  ProjectRef,
  TaskStatus,
} from "@/client"
import { nameList, plural } from "@/components/Common/words"
import type { RecordKind } from "@/components/Records/panels"
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

/** The record one entry links to: its own entity, or the task a comment or
 * file is on. `null` when the entry names no single record at all — a
 * batch, or a row whose real entity the backend could not place (`kind:
 * "unrecognized"`) and whose own type carries no such entity. */
export interface RecordRef {
  kind: RecordKind
  id: string
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

/**
 * What a batch did, in the words the reader will recognise.
 *
 * The `status === "done"` test below is one of three places that decide
 * whether a batch counts as a completion rather than a plain status move
 * (#321): `app.activity_log._BULK_COMPLETION` (Python) is what the log's
 * own `kind=completed` filter narrows by, and `app.mcp.tools.
 * search_activity._describe_batch_changes` decides the same thing a third
 * time for the MCP tool's narration. A shared constant cannot cross the
 * Python/TypeScript line here — the generated client carries a shape
 * (`TasksBulkChangedDetailsPublic`, the `TaskStatus` union), never a
 * predicate — so nothing ties the three together but this comment and
 * `backend/tests/app/test_batch_completion_rule.py`, which guards the two
 * Python sites directly; this file's own `entryWords.test.ts` guards this
 * one against drifting on its own.
 */
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
  ].filter(Boolean) as string[]
  return said.length ? nameList(said) : "changed the tags"
}

/** A sentence with nothing after the verb and no subject of its own. */
function whole(verb: string): EntryWords {
  return { verb, subject: false, after: "" }
}

/** A sentence whose subject the caller fills in. */
function withSubject(verb: string, after = ""): EntryWords {
  return { verb, subject: true, after }
}

// The implicit-voice sentence for a deletion or a restore reads the same
// whether the entry is a single task's own or a batch's: the task panel is
// always open on one task, so it never has a count or a selection to speak
// of either way (#321). One value for each, shared by both of a kind's two
// switch cases below, rather than written out twice.
const DELETED_IMPLICIT = whole("deleted it")
const RESTORED_IMPLICIT = whole("restored it")

/** The record a task-kind entry links to: itself, by the id every entry of
 * any kind already carries. */
function taskRecord(entry: ActivityEntryPublic): RecordRef {
  return { kind: "task", id: entry.entity_id }
}

function projectRecord(entry: ActivityEntryPublic): RecordRef {
  return { kind: "project", id: entry.entity_id }
}

function tagRecord(entry: ActivityEntryPublic): RecordRef {
  return { kind: "tag", id: entry.entity_id }
}

/**
 * Everything one action's entry has to say: both voices' sentences, the name
 * of the subject the log page links to, and the record that link opens.
 */
interface ActionVoices {
  /** What the log page says: it names every one of the 24 actions. */
  names: EntryWords
  /** What the task panel says, or `null` for an action it does not speak. */
  implicit: EntryWords | null
  /** The subject's display name, independent of voice — the task panel
   * never shows it, but computing it costs nothing extra here. */
  subjectName: string
  /** The record the subject links to, or `null` when the entry names none. */
  record: RecordRef | null
}

/**
 * The 24 kinds of activity entry, each as both of its voices, its subject's
 * name and the record that subject links to — one switch, declared here
 * because this is the one place that reads `entry.details.kind` at all.
 *
 * It is built from what the entry recorded at the time, so it reads the
 * same after the task, project or tag is renamed, moved or deleted — only
 * the record's link depends on the thing still being there.
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
 * The switch has no `default`: every one of the 27 cases (24 actions, two of
 * them split into a `_batch` sibling, plus `unrecognized`) must return an
 * `ActionVoices`, or the function falls off the end without one, and the
 * compiler rejects it — a 25th kind with no case here yet is a type error
 * wherever this file's exports are called, not a silent fallback.
 *
 * The two voices are not the same sentence twice over: `subject-implicit`
 * is addressed to a reader who already has the record open (the task
 * panel), so it says less, and sometimes says nothing at all — a comment,
 * a project or a tag is not among the actions it speaks, so `implicit` is
 * `null` for those, declared so rather than reached by falling through a
 * conditional. `names-its-subject` speaks every action, because the log
 * page is the one place every kind of entry is read.
 */
function actionVoices(
  entry: ActivityEntryPublic,
  currentUserId: string | undefined,
): ActionVoices {
  const { details } = entry

  switch (details.kind) {
    case "task_created": {
      const { task } = details
      return {
        subjectName: details.title ?? "Untitled task",
        record: taskRecord(entry),
        names: withSubject(
          "Created",
          task.project ? ` in ${projectName(task.project)}` : "",
        ),
        // Unlike the other voice, this only mentions the project when it
        // has a name — a project reference with none reads as if there
        // were no project at all, rather than naming it "no longer exists".
        implicit: whole(
          task.project?.name
            ? `created this in ${task.project.name}`
            : "created this",
        ),
      }
    }
    case "task_changed": {
      const said = changedFields(details.changes)
      const fields = Object.keys(details.changes).map(
        (key) => FIELD_LABELS[key] ?? key,
      )
      return {
        subjectName: details.title ?? "Untitled task",
        record: taskRecord(entry),
        names: withSubject(`Changed the ${fields.join(", ")} of`),
        implicit: said ? whole(said) : null,
      }
    }
    case "task_completed":
      return {
        subjectName: details.title ?? "Untitled task",
        record: taskRecord(entry),
        names: withSubject("Completed"),
        implicit: whole("completed it"),
      }
    case "task_reopened":
      return {
        subjectName: details.title ?? "Untitled task",
        record: taskRecord(entry),
        names: withSubject("Reopened"),
        implicit: whole("reopened it"),
      }
    case "task_status_changed": {
      const { to } = details
      return {
        subjectName: details.title ?? "Untitled task",
        record: taskRecord(entry),
        names: withSubject(
          "Moved",
          ` to ${to ? STATUS_LABELS[to] : "another status"}`,
        ),
        implicit: whole(to ? `moved it to ${STATUS_LABELS[to]}` : "moved it"),
      }
    }
    case "task_deleted": {
      const subtasks = details.subtask_count ?? 0
      return {
        subjectName: details.title ?? "Untitled task",
        record: taskRecord(entry),
        names: withSubject(
          "Deleted",
          subtasks > 0 ? ` and ${plural(subtasks, "subtask")}` : "",
        ),
        implicit: DELETED_IMPLICIT,
      }
    }
    case "task_deleted_batch":
      // A batch names no single task: what it deleted is the selection, and
      // the count is what the entry has to say.
      return {
        subjectName: "Untitled task",
        record: taskRecord(entry),
        names: whole(`Deleted ${plural(details.task_count, "task")}`),
        implicit: DELETED_IMPLICIT,
      }
    case "task_restored": {
      const subtasks = details.subtask_count ?? 0
      return {
        subjectName: details.title ?? "Untitled task",
        record: taskRecord(entry),
        names: withSubject(
          "Restored",
          subtasks > 0 ? ` and ${plural(subtasks, "subtask")}` : "",
        ),
        implicit: RESTORED_IMPLICIT,
      }
    }
    case "task_restored_batch":
      return {
        subjectName: "Untitled task",
        record: taskRecord(entry),
        names: whole(`Restored ${plural(details.task_count, "task")}`),
        implicit: RESTORED_IMPLICIT,
      }
    case "task_moved": {
      const to = details.to_project
      return {
        subjectName: details.title ?? "Untitled task",
        record: taskRecord(entry),
        names: withSubject(
          "Moved",
          ` from ${projectName(details.from_project)} to ${projectName(
            details.to_project,
          )}`,
        ),
        // Only the destination, not the origin: the task panel already
        // knows where the task was, because it is reading its history in
        // order.
        implicit: whole(
          to?.name ? `moved it to ${to.name}` : "moved it to another project",
        ),
      }
    }
    case "task_assigned": {
      const { assignee } = details
      // The only human a task can be assigned to is its owner: when they
      // did it themselves it is "yourself", when a bot user did it, "you".
      const who =
        assignee?.type === "bot_user"
          ? (assignee.name ?? "a bot user")
          : entry.actor_bot_user_id
            ? "you"
            : "yourself"
      return {
        subjectName: details.title ?? "Untitled task",
        record: taskRecord(entry),
        names: withSubject(
          "Assigned",
          ` to ${namesAssignee(assignee, details.assignee_id ?? undefined, currentUserId)}`,
        ),
        implicit: whole(`assigned it to ${who}`),
      }
    }
    case "task_unassigned": {
      const previous = details.previous_assignee
      return {
        subjectName: details.title ?? "Untitled task",
        record: taskRecord(entry),
        names:
          previous?.type === "bot_user"
            ? withSubject(
                `Removed ${namesAssignee(previous, previous.id, currentUserId)} from`,
              )
            : withSubject("Removed the assignee from"),
        // Unlike the other voice, this never names who was removed, bot
        // user or not — "removed the assignee" covers every case.
        implicit: whole("removed the assignee"),
      }
    }
    case "tasks_bulk_changed": {
      const { task_count: count } = details
      const batch = describeBatch(details.changes)
      // The current task is one of the count; what matters to the implicit
      // voice is how many others went with it.
      const others = count - 1
      return {
        subjectName: "Untitled task",
        record: taskRecord(entry),
        names: whole(
          `Changed ${plural(count, "task")}${batch ? `: ${batch}` : ""}`,
        ),
        implicit: whole(
          others > 0
            ? `changed it along with ${others} other ${others === 1 ? "task" : "tasks"}`
            : "changed it",
        ),
      }
    }
    // `subjectName` and `record` below are getters, not plain fields, in
    // these five cases only: both read through `details.task`, which
    // `names`/`implicit` never touch, and a caller that only wants the
    // sentence (`entryWords`, and the fixtures `entryWords.test.ts` builds
    // for exactly that) should not have to supply one.
    case "attachment_added": {
      const { filename } = details
      return {
        get subjectName() {
          return details.task.title ?? "a task"
        },
        get record() {
          return { kind: "task" as const, id: details.task.id }
        },
        names: withSubject(`Attached “${filename}” to`),
        implicit: whole(`attached “${filename}”`),
      }
    }
    case "attachment_deleted": {
      const { filename } = details
      return {
        get subjectName() {
          return details.task.title ?? "a task"
        },
        get record() {
          return { kind: "task" as const, id: details.task.id }
        },
        names: withSubject(`Removed “${filename}” from`),
        implicit: whole(`removed “${filename}”`),
      }
    }
    // A comment is shown as the comment itself, with its author and body,
    // not as a line saying someone wrote one — so the task panel's voice
    // has nothing to say about these.
    case "comment_added":
      return {
        get subjectName() {
          return details.task.title ?? "a task"
        },
        get record() {
          return { kind: "task" as const, id: details.task.id }
        },
        names: withSubject("Commented on"),
        implicit: null,
      }
    case "comment_edited":
      return {
        get subjectName() {
          return details.task.title ?? "a task"
        },
        get record() {
          return { kind: "task" as const, id: details.task.id }
        },
        names: withSubject("Edited a comment on"),
        implicit: null,
      }
    case "comment_deleted":
      return {
        get subjectName() {
          return details.task.title ?? "a task"
        },
        get record() {
          return { kind: "task" as const, id: details.task.id }
        },
        names: withSubject("Deleted a comment on"),
        implicit: null,
      }
    // Projects and tags never appear in a task's own history, so the task
    // panel's voice has nothing to say about these either.
    case "project_created":
      return {
        subjectName: details.name ?? "Untitled project",
        record: projectRecord(entry),
        names: withSubject("Created the project"),
        implicit: null,
      }
    case "project_changed":
      return {
        subjectName: details.name ?? "Untitled project",
        record: projectRecord(entry),
        names: withSubject(
          `Changed the ${Object.keys(details.changes).join(", ")} of the project`,
        ),
        implicit: null,
      }
    case "project_deleted": {
      const tasks = details.task_count
      return {
        subjectName: details.name ?? "Untitled project",
        record: projectRecord(entry),
        names: withSubject(
          "Deleted the project",
          tasks > 0 ? ` and ${plural(tasks, "task")}` : "",
        ),
        implicit: null,
      }
    }
    case "project_restored": {
      const tasks = details.task_count
      return {
        subjectName: details.name ?? "Untitled project",
        record: projectRecord(entry),
        names: withSubject(
          "Restored the project",
          tasks > 0 ? ` and ${plural(tasks, "task")}` : "",
        ),
        implicit: null,
      }
    }
    case "tag_created":
      return {
        // "Untitled project" covers a nameless tag too — an existing
        // wording quirk, preserved rather than fixed, since nothing
        // user-visible changes in this ticket.
        subjectName: details.name ?? "Untitled project",
        record: tagRecord(entry),
        names: withSubject("Created the tag"),
        implicit: null,
      }
    case "tag_renamed":
      return {
        subjectName: details.name ?? "Untitled project",
        record: tagRecord(entry),
        names: withSubject(
          `Renamed the tag “${details.changes.name?.from}” to`,
        ),
        implicit: null,
      }
    case "tag_merged": {
      const { sources, task_count: tasks } = details
      return {
        subjectName: details.name ?? "Untitled project",
        record: tagRecord(entry),
        names: withSubject(
          `Merged ${sources.map((name) => `“${name}”`).join(", ")} into`,
          tasks > 0 ? `, moving ${plural(tasks, "task")} onto it` : "",
        ),
        implicit: null,
      }
    }
    case "tag_deleted": {
      const tasks = details.task_count
      return {
        subjectName: details.name ?? "Untitled project",
        record: tagRecord(entry),
        names: withSubject(
          "Deleted the tag",
          tasks > 0 ? `, taking it off ${plural(tasks, "task")}` : "",
        ),
        implicit: null,
      }
    }
    // A row the backend itself could not make sense of (`app.activity_details
    // .to_public`'s own fallback) — one bad entry says so plainly rather
    // than breaking the page it would otherwise take down with it. Its real
    // entity is still named by `entity_type`/`entity_id` even though
    // `details` carries nothing else, so the record link survives for a
    // task, project or tag; a comment or an attachment has no `details.task`
    // left to point through, so the link is dropped rather than guessed at.
    case "unrecognized":
      return {
        subjectName: "Untitled task",
        record:
          entry.entity_type === "task" ||
          entry.entity_type === "project" ||
          entry.entity_type === "tag"
            ? { kind: entry.entity_type, id: entry.entity_id }
            : null,
        names: whole("Something changed"),
        implicit: null,
      }
  }
}

/**
 * One entry's sentence, in the given voice: an entry plus a voice in,
 * sentence parts or `null` out. A caller in `names-its-subject` should never
 * actually see `null` — every action has a sentence in that voice — but the
 * return type stays nullable for both, so a 25th action with no case yet in
 * `actionVoices` fails to compile here rather than throwing at runtime.
 */
export function entryWords(
  entry: ActivityEntryPublic,
  voice: Voice,
  currentUserId?: string,
): EntryWords | null {
  const voices = actionVoices(entry, currentUserId)
  return voice === "subject-implicit" ? voices.implicit : voices.names
}

/**
 * What an entry names: the task, project, tag, or task a comment or file is
 * on. Reads the same per-action declaration `entryWords` does, so a 25th
 * action with no case there is a compile error here too, rather than a
 * silent fallback to "Untitled task".
 */
export function subjectName(entry: ActivityEntryPublic): string {
  return actionVoices(entry, undefined).subjectName
}

/**
 * The record an entry links to: its own entity, or for a comment or a file,
 * the task it is on. `null` when the entry names no single record (a batch,
 * or an unrecognized row whose real entity was itself a comment or
 * attachment).
 */
export function recordOf(entry: ActivityEntryPublic): RecordRef | null {
  return actionVoices(entry, undefined).record
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
