import { Link } from "@tanstack/react-router"
import type { ReactNode } from "react"

import type { ActivityEntryPublic } from "@/client"

interface ProjectRef {
  id: string
  name: string | null
}

// What each field is called when an entry lists what changed.
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
  if ("completed" in changes) {
    said.push(changes.completed ? "completed" : "reopened")
  }
  if ("priority" in changes) {
    said.push(
      changes.priority ? `priority ${changes.priority}` : "priority cleared",
    )
  }
  if ("due_date" in changes) {
    said.push(changes.due_date ? `due ${changes.due_date}` : "due date cleared")
  }
  const project = changes.project as { name?: string } | undefined
  if (project?.name) said.push(`moved to ${project.name}`)
  const added = changes.added_tags as string[] | undefined
  if (added?.length) said.push(`tagged ${added.join(", ")}`)
  const removed = changes.removed_tags as string[] | undefined
  if (removed?.length) said.push(`untagged ${removed.join(", ")}`)
  return said.join(", ")
}

function detail<T>(entry: ActivityEntryPublic, key: string): T | undefined {
  return entry.details[key] as T | undefined
}

function projectName(project: ProjectRef | null | undefined): string {
  return project?.name ?? "a project that no longer exists"
}

// Entries from before bot users could be assigned carry only the id.
interface AssigneeRef {
  type: "user" | "bot_user"
  id: string
  name?: string
}

/**
 * Who a task was assigned to. A bot user is named as it was called at the
 * time, which still reads after it is renamed or deleted.
 */
function assigneeName(
  assignee: AssigneeRef | null | undefined,
  assigneeId: string | undefined,
  currentUserId: string | undefined,
): string {
  if (assignee?.type === "bot_user") {
    return `the bot user ${assignee.name}`
  }
  return (assignee?.id ?? assigneeId) === currentUserId ? "you" : "someone"
}

interface ActivityDescriptionProps {
  entry: ActivityEntryPublic
  currentUserId?: string
}

/**
 * What an entry names: the task, project, tag, or task a comment or file is
 * on.
 */
function subjectName(entry: ActivityEntryPublic): string {
  if (entry.entity_type === "project" || entry.entity_type === "tag") {
    return detail<string>(entry, "name") ?? "Untitled project"
  }
  if (entry.entity_type === "comment" || entry.entity_type === "attachment") {
    return detail<{ title: string }>(entry, "task")?.title ?? "a task"
  }
  return detail<string>(entry, "title") ?? "Untitled task"
}

/**
 * One entry as a sentence. It is built from what the entry recorded at the
 * time, so it reads the same after the task is renamed, moved or deleted;
 * only the link depends on the thing still being there.
 */
export function ActivityDescription({
  entry,
  currentUserId,
}: ActivityDescriptionProps) {
  const name = subjectName(entry)
  const linkClass = "font-medium underline-offset-4 hover:underline"

  // A task opens its panel on the screen the reader is already on — `to="."`
  // is the current route — so following a link from a long log does not cost
  // them their place in it. A project or a tag has no panel, so it falls back
  // to the task list narrowed to it; dropping the reader on the unfiltered
  // list would make the link a lie.
  const subject: ReactNode = !entry.entity_exists ? (
    <span className="font-medium">{name}</span>
  ) : entry.entity_type === "task" ? (
    <Link
      to="."
      search={(previous: Record<string, unknown>) => ({
        ...previous,
        task: entry.entity_id,
      })}
      className={linkClass}
    >
      {name}
    </Link>
  ) : (
    <Link
      to="/tasks"
      search={{ project_id: entry.entity_project_id ?? undefined }}
      className={linkClass}
    >
      {name}
    </Link>
  )

  switch (entry.action) {
    case "task_created": {
      const snapshot = detail<{ project: ProjectRef | null }>(entry, "task")
      return (
        <>
          Created {subject}
          {snapshot?.project && <> in {projectName(snapshot.project)}</>}
        </>
      )
    }
    case "task_changed": {
      const changes = detail<Record<string, unknown>>(entry, "changes") ?? {}
      const fields = Object.keys(changes).map((key) => FIELD_LABELS[key] ?? key)
      return (
        <>
          Changed the {fields.join(", ")} of {subject}
        </>
      )
    }
    case "task_completed":
      return <>Completed {subject}</>
    case "task_reopened":
      return <>Marked {subject} as not completed</>
    case "task_deleted": {
      // A batch names no single task: what it deleted is the selection, and
      // the count is what the entry has to say.
      const batch = detail<number>(entry, "task_count")
      if (batch !== undefined) {
        return <>Deleted {batch === 1 ? "1 task" : `${batch} tasks`}</>
      }
      const subtasks = detail<number>(entry, "subtask_count") ?? 0
      return (
        <>
          Deleted {subject}
          {subtasks > 0 &&
            ` and ${subtasks} ${subtasks === 1 ? "subtask" : "subtasks"}`}
        </>
      )
    }
    case "tasks_bulk_changed": {
      const count = detail<number>(entry, "task_count") ?? 0
      const changes = detail<Record<string, unknown>>(entry, "changes") ?? {}
      return (
        <>
          Changed {count === 1 ? "1 task" : `${count} tasks`}
          {describeBatch(changes) && `: ${describeBatch(changes)}`}
        </>
      )
    }
    case "task_restored": {
      const subtasks = detail<number>(entry, "subtask_count") ?? 0
      return (
        <>
          Restored {subject}
          {subtasks > 0 &&
            ` and ${subtasks} ${subtasks === 1 ? "subtask" : "subtasks"}`}
        </>
      )
    }
    case "task_moved":
      return (
        <>
          Moved {subject} from{" "}
          {projectName(detail<ProjectRef>(entry, "from_project"))} to{" "}
          {projectName(detail<ProjectRef>(entry, "to_project"))}
        </>
      )
    case "task_assigned":
      return (
        <>
          Assigned {subject} to{" "}
          {assigneeName(
            detail<AssigneeRef>(entry, "assignee"),
            detail<string>(entry, "assignee_id"),
            currentUserId,
          )}
        </>
      )
    case "task_unassigned": {
      const previous = detail<AssigneeRef>(entry, "previous_assignee")
      if (previous?.type === "bot_user") {
        return (
          <>
            Removed {assigneeName(previous, previous.id, currentUserId)} from{" "}
            {subject}
          </>
        )
      }
      return <>Removed the assignee from {subject}</>
    }
    case "project_created":
      return <>Created the project {subject}</>
    case "project_changed": {
      const changes = detail<Record<string, unknown>>(entry, "changes") ?? {}
      return (
        <>
          Changed the {Object.keys(changes).join(", ")} of the project {subject}
        </>
      )
    }
    case "project_deleted": {
      const tasks = detail<number>(entry, "task_count") ?? 0
      return (
        <>
          Deleted the project {subject}
          {tasks > 0 && ` and ${tasks} ${tasks === 1 ? "task" : "tasks"}`}
        </>
      )
    }
    case "project_restored": {
      const tasks = detail<number>(entry, "task_count") ?? 0
      return (
        <>
          Restored the project {subject}
          {tasks > 0 && ` and ${tasks} ${tasks === 1 ? "task" : "tasks"}`}
        </>
      )
    }
    case "comment_added":
      return <>Commented on {subject}</>
    case "comment_edited":
      return <>Edited a comment on {subject}</>
    case "comment_deleted":
      return <>Deleted a comment on {subject}</>
    case "attachment_added":
      return (
        <>
          Attached “{detail<string>(entry, "filename")}” to {subject}
        </>
      )
    case "attachment_deleted":
      return (
        <>
          Removed “{detail<string>(entry, "filename")}” from {subject}
        </>
      )
    case "tag_created":
      return <>Created the tag {subject}</>
    case "tag_renamed": {
      const change = detail<{ name?: { from: string } }>(entry, "changes")
      return (
        <>
          Renamed the tag “{change?.name?.from}” to {subject}
        </>
      )
    }
    case "tag_merged": {
      const sources = detail<string[]>(entry, "sources") ?? []
      const tasks = detail<number>(entry, "task_count") ?? 0
      return (
        <>
          Merged {sources.map((name) => `“${name}”`).join(", ")} into {subject}
          {tasks > 0 &&
            `, moving ${tasks} ${tasks === 1 ? "task" : "tasks"} onto it`}
        </>
      )
    }
    case "tag_deleted": {
      const tasks = detail<number>(entry, "task_count") ?? 0
      return (
        <>
          Deleted the tag {subject}
          {tasks > 0 &&
            `, taking it off ${tasks} ${tasks === 1 ? "task" : "tasks"}`}
        </>
      )
    }
  }
}
