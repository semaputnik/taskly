import { Link } from "@tanstack/react-router"

import type { TagPublic } from "@/client"
import { cn } from "@/lib/utils"
import { archivedNote, taskCountLabel } from "./counts"

/**
 * A tag's live task count, linked to the task list it has to agree with, and
 * what it leaves out said beside it (FR-01.26).
 */
export function TaskCount({
  tag,
  className,
}: {
  tag: TagPublic
  className?: string
}) {
  const count = tag.task_count ?? 0
  const archived = archivedNote(tag)
  return (
    <span className="flex flex-wrap items-baseline gap-x-2">
      {count === 0 ? (
        <span className={cn("text-muted-foreground italic", className)}>
          No tasks
        </span>
      ) : (
        <Link
          to="/tasks"
          search={{ tag: tag.name }}
          className={cn("underline-offset-4 hover:underline", className)}
        >
          {taskCountLabel(count)}
        </Link>
      )}
      {archived && (
        <span className="text-muted-foreground text-xs">{archived}</span>
      )}
    </span>
  )
}
