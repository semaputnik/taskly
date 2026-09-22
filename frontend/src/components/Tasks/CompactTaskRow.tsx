import { Link as RouterLink } from "@tanstack/react-router"
import {
  CalendarDays,
  CornerDownRight,
  ListTree,
  Repeat,
  Tag,
} from "lucide-react"

import type { TaskPublic } from "@/client"
import { recordLink } from "@/components/Records/panels"
import { Skeleton } from "@/components/ui/skeleton"
import { isoDay } from "@/lib/dates"
import { cn } from "@/lib/utils"
import { CompleteTask } from "./CompleteTask"
import { type DueTone, describeDue, subtaskProgress } from "./compact"
import { describeRecurrence } from "./recurrence"

const DUE_TONE: Record<DueTone, string> = {
  late: "text-destructive",
  today: "text-foreground",
  soon: "text-muted-foreground",
  later: "text-muted-foreground",
}

/**
 * A task in two short lines: the checkbox, carrying the priority in its ring,
 * and the title; then what there is to know at a glance — how far through its
 * subtasks it is, when it is due, and its tags. A line with nothing to say is
 * not drawn, so an undated, untagged task is one line tall.
 *
 * It is the dashboard's row and the task list's compact view. It opens the
 * task from its title, never the whole row: the row also holds the checkbox,
 * and a checkbox inside a link is a trap.
 */
export function CompactTaskRow({
  task,
  projectName,
}: {
  task: TaskPublic
  /** Shown at the end of the title line, from `sm` up. */
  projectName?: string
}) {
  const done = task.status === "done"
  const progress = subtaskProgress(task)
  const due = task.due_date
    ? describeDue(task.due_date, isoDay(new Date()), { done })
    : null
  const tags = task.tags ?? []
  const hasMeta = progress || due || task.recurrence || tags.length > 0

  return (
    <div className="hover:bg-muted/50 flex gap-3 border-b px-4 py-2.5 transition-colors last:border-b-0">
      {/* Nudged onto the title's line box so the two share a centre. */}
      <CompleteTask
        task={task}
        showPriority
        className="mt-px size-[1.125rem]"
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {task.parent_id && (
            <CornerDownRight
              className="text-muted-foreground size-3.5 shrink-0"
              aria-label="Subtask"
            />
          )}
          <RouterLink
            {...recordLink("task", task.id)}
            className={cn(
              "min-w-0 flex-1 truncate text-sm font-medium underline-offset-4 hover:underline",
              done && "text-muted-foreground line-through",
            )}
          >
            {task.title}
          </RouterLink>
          {projectName && (
            // Capped and truncated: a long project name must not squeeze the
            // task's own title out of its row.
            <span className="text-muted-foreground hidden max-w-[40%] shrink-0 truncate text-xs sm:inline">
              {projectName}
            </span>
          )}
        </div>

        {hasMeta && (
          <div className="text-muted-foreground mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
            {progress && (
              <span className="flex items-center gap-1 tabular-nums">
                <ListTree className="size-3.5 shrink-0" aria-hidden />
                <span className="sr-only">Subtasks done:</span>
                {progress}
              </span>
            )}
            {due && (
              <span
                className={cn("flex items-center gap-1", DUE_TONE[due.tone])}
              >
                <CalendarDays className="size-3.5 shrink-0" aria-hidden />
                <span className="sr-only">Due:</span>
                {due.text}
              </span>
            )}
            {task.recurrence && (
              <span className="flex items-center gap-1">
                <Repeat className="size-3.5 shrink-0" aria-hidden />
                {describeRecurrence(task.recurrence)}
              </span>
            )}
            {tags.map((tag) => (
              <span key={tag} className="flex min-w-0 items-center gap-1">
                <Tag className="size-3.5 shrink-0" aria-hidden />
                <span className="sr-only">Tag:</span>
                <span className="truncate">{tag}</span>
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

/** The row while its task is on its way: the same two lines, in outline. */
export function CompactTaskRowPending() {
  return (
    <div className="flex gap-3 border-b px-4 py-2.5 last:border-b-0">
      <Skeleton className="mt-px size-[1.125rem] shrink-0 rounded-full" />
      <div className="flex flex-1 flex-col gap-1.5">
        <Skeleton className="h-4 w-48 max-w-full" />
        <Skeleton className="h-3 w-24" />
      </div>
    </div>
  )
}
