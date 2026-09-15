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

function detail<T>(entry: ActivityEntryPublic, key: string): T | undefined {
  return entry.details[key] as T | undefined
}

function projectName(project: ProjectRef | null | undefined): string {
  return project?.name ?? "a project that no longer exists"
}

interface ActivityDescriptionProps {
  entry: ActivityEntryPublic
  currentUserId?: string
}

/**
 * One entry as a sentence. It is built from what the entry recorded at the
 * time, so it reads the same after the task is renamed, moved or deleted;
 * only the link to the task depends on the task still being there.
 */
export function ActivityDescription({
  entry,
  currentUserId,
}: ActivityDescriptionProps) {
  const title = detail<string>(entry, "title") ?? "Untitled task"
  const task: ReactNode = entry.entity_exists ? (
    <Link
      to="/tasks"
      search={{ project_id: entry.entity_project_id ?? undefined }}
      className="font-medium underline-offset-4 hover:underline"
    >
      {title}
    </Link>
  ) : (
    <span className="font-medium">{title}</span>
  )

  switch (entry.action) {
    case "task_created": {
      const snapshot = detail<{ project: ProjectRef | null }>(entry, "task")
      return (
        <>
          Created {task}
          {snapshot?.project && <> in {projectName(snapshot.project)}</>}
        </>
      )
    }
    case "task_changed": {
      const changes = detail<Record<string, unknown>>(entry, "changes") ?? {}
      const fields = Object.keys(changes).map((key) => FIELD_LABELS[key] ?? key)
      return (
        <>
          Changed the {fields.join(", ")} of {task}
        </>
      )
    }
    case "task_completed":
      return <>Completed {task}</>
    case "task_reopened":
      return <>Marked {task} as not completed</>
    case "task_deleted": {
      const subtasks = detail<number>(entry, "subtask_count") ?? 0
      return (
        <>
          Deleted {task}
          {subtasks > 0 &&
            ` and ${subtasks} ${subtasks === 1 ? "subtask" : "subtasks"}`}
        </>
      )
    }
    case "task_moved":
      return (
        <>
          Moved {task} from{" "}
          {projectName(detail<ProjectRef>(entry, "from_project"))} to{" "}
          {projectName(detail<ProjectRef>(entry, "to_project"))}
        </>
      )
    case "task_assigned": {
      const assignee = detail<string>(entry, "assignee_id")
      return (
        <>
          Assigned {task} to {assignee === currentUserId ? "you" : "someone"}
        </>
      )
    }
    case "task_unassigned":
      return <>Removed the assignee from {task}</>
  }
}
