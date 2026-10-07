import type { ActivityEntryPublic, TaskStatus } from "@/client"
import { formatDay } from "@/lib/dates"
import { STATUS_LABELS } from "./statuses"

/**
 * What one log entry says about a task, as the rest of a sentence whose
 * subject is whoever made the change: "moved it to In progress", "set the due
 * date to 7 Oct". The task panel shows its history as a chronology of
 * these, so every line leaves the task out: it is the one the panel is open
 * on.
 *
 * Comments return nothing: a comment is shown as the comment itself, with its
 * author and body, not as a line saying someone wrote one. Everything the log
 * records about a task that this does not know how to say returns nothing as
 * well, rather than a line that reads wrongly.
 */
export function describeTaskEvent(entry: ActivityEntryPublic): string | null {
  const details = entry.details
  const by = (key: string) => details[key] as unknown
  switch (entry.action) {
    case "task_created": {
      const project = (by("task") as { project?: { name?: string } | null })
        ?.project
      return project?.name ? `created this in ${project.name}` : "created this"
    }
    case "task_changed":
      return changedFields(
        (by("changes") ?? {}) as Record<string, { from: unknown; to: unknown }>,
      )
    case "task_completed":
      return "completed it"
    case "task_reopened":
      return "reopened it"
    case "task_status_changed": {
      const to = by("to") as TaskStatus | undefined
      return to ? `moved it to ${STATUS_LABELS[to]}` : "moved it"
    }
    case "task_moved": {
      const to = by("to_project") as { name?: string } | null
      return to?.name ? `moved it to ${to.name}` : "moved it to another project"
    }
    case "task_assigned":
      return `assigned it to ${assignee(entry)}`
    case "task_unassigned":
      return "removed the assignee"
    case "task_deleted":
      return "deleted it"
    case "task_restored":
      return "restored it"
    case "tasks_bulk_changed": {
      const others = ((by("task_count") as number | undefined) ?? 1) - 1
      return others > 0
        ? `changed it along with ${others} other ${others === 1 ? "task" : "tasks"}`
        : "changed it"
    }
    case "attachment_added":
      return `attached “${by("filename")}”`
    case "attachment_deleted":
      return `removed “${by("filename")}”`
    default:
      return null
  }
}

function assignee(entry: ActivityEntryPublic): string {
  const who = entry.details.assignee as
    | { type: "user" | "bot_user"; name?: string }
    | null
    | undefined
  if (who?.type === "bot_user") return who.name ?? "a bot user"
  // The only human a task can be assigned to is its owner: when they did it
  // themselves it is "yourself", when a bot user did it, "you".
  return entry.actor_bot_user_id ? "you" : "yourself"
}

type Change = { from: unknown; to: unknown }

function changedFields(changes: Record<string, Change>): string | null {
  const said: string[] = []
  if (changes.title) said.push(`renamed it to “${changes.title.to}”`)
  if (changes.description) said.push("edited the description")
  if (changes.due_date) {
    said.push(
      changes.due_date.to
        ? `set the due date to ${formatDay(changes.due_date.to as string)}`
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
