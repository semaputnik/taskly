import type { ColumnDef } from "@tanstack/react-table"
import { CornerDownRight, Repeat } from "lucide-react"

import type { TaskPublic } from "@/client"
import type { DataTableFeatures } from "@/components/Common/DataTable"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { formatDay, formatDayOf } from "@/lib/dates"
import { cn } from "@/lib/utils"
import { CompleteTask } from "./CompleteTask"
import { PriorityBadge } from "./priority"
import { describeRecurrence } from "./recurrence"
import { STATUS_LABELS, StatusGlyph, StatusMenu } from "./status"

interface ColumnOptions {
  /**
   * Show the tasks without any way to change them: an archived project's tasks
   * are read-only until it is unarchived (FR-05.12).
   */
  readOnly?: boolean
  /**
   * Completing a task takes its row out of this table, so the checkbox
   * confirms the move and offers the way back (ADR-0006).
   */
  receipt?: boolean
}

export function getColumns(
  projectNames: Record<string, string>,
  _depths: Record<string, number>,
  { readOnly = false, receipt = false }: ColumnOptions = {},
): ColumnDef<DataTableFeatures, TaskPublic>[] {
  const columns: ColumnDef<DataTableFeatures, TaskPublic>[] = [
    {
      accessorKey: "title",
      header: "Title",
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          {/* Completion sits with the task it is about. The checkbox in the
              first column selects the row for a batch, which is what a square
              check means in a list that can act on many rows at once. */}
          {readOnly ? (
            <Checkbox
              className="rounded-full"
              checked={row.original.status === "done"}
              disabled
              aria-label={STATUS_LABELS[row.original.status]}
            />
          ) : (
            <CompleteTask task={row.original} receipt={receipt} />
          )}
          {/* A subtask says so for itself. Indenting it instead would claim a
              parent–child relationship the row above may not have: sorting or
              filtering can put any two rows next to each other, and the parent
              may not be in the list at all. */}
          {row.original.parent_id && (
            <CornerDownRight
              className="text-muted-foreground size-3.5 shrink-0"
              aria-label="Subtask"
            />
          )}
          <span
            className={cn(
              "font-medium",
              row.original.status === "done" &&
                "line-through text-muted-foreground",
            )}
          >
            {row.original.title}
          </span>
          {row.original.recurrence && (
            <Badge variant="outline" className="gap-1 text-xs">
              <Repeat className="size-3" />
              {describeRecurrence(row.original.recurrence)}
            </Badge>
          )}
        </div>
      ),
    },
    {
      // Next to the title it describes. A glyph that is told apart by shape,
      // with its label, so the column reads without colour.
      id: "status",
      header: "Status",
      cell: ({ row }) =>
        readOnly ? (
          <span className="text-muted-foreground flex items-center gap-1.5">
            <StatusGlyph status={row.original.status} />
            <span className="hidden sm:inline">
              {STATUS_LABELS[row.original.status]}
            </span>
            <span className="sr-only sm:hidden">
              {STATUS_LABELS[row.original.status]}
            </span>
          </span>
        ) : (
          <StatusMenu task={row.original} />
        ),
    },
    {
      id: "project",
      header: "Project",
      cell: ({ row }) => (
        <span className="text-muted-foreground">
          {projectNames[row.original.project_id] ?? "Unknown"}
        </span>
      ),
    },
    {
      accessorKey: "due_date",
      header: "Due date",
      cell: ({ row }) => {
        const dueDate = row.original.due_date
        return (
          <span className={cn("text-muted-foreground", !dueDate && "italic")}>
            {dueDate ? formatDay(dueDate) : "No due date"}
          </span>
        )
      },
    },
    {
      id: "tags",
      header: "Tags",
      cell: ({ row }) => {
        const tags = row.original.tags ?? []
        return tags.length ? (
          <div className="flex flex-wrap gap-1">
            {tags.map((tag) => (
              <Badge key={tag} variant="secondary">
                {tag}
              </Badge>
            ))}
          </div>
        ) : (
          <span className="text-muted-foreground italic">No tags</span>
        )
      },
    },
    {
      accessorKey: "priority",
      header: "Priority",
      cell: ({ row }) => {
        const priority = row.original.priority
        return priority ? (
          <PriorityBadge priority={priority} />
        ) : (
          <span className="text-muted-foreground italic">No priority</span>
        )
      },
    },
    {
      // Last, after the columns a reader scans. The table already scrolls
      // sideways, so the scroll should cost the least-read column, not the
      // title or the due date. The day here; the panel gives the moment.
      accessorKey: "created_at",
      header: "Created",
      cell: ({ row }) => {
        const createdAt = row.original.created_at
        return (
          <span className={cn("text-muted-foreground", !createdAt && "italic")}>
            {createdAt ? formatDayOf(createdAt) : "Unknown"}
          </span>
        )
      },
    },
  ]

  // No row menu: editing, adding a subtask and deleting all live in the task's
  // detail panel, which the row opens. One place to act on a task beats the
  // same three items repeated on every line.
  return columns
}
