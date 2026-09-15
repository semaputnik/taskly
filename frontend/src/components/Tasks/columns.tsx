import type { ColumnDef } from "@tanstack/react-table"
import { CornerDownRight, Repeat } from "lucide-react"

import type { TaskPublic } from "@/client"
import type { DataTableFeatures } from "@/components/Common/DataTable"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { cn } from "@/lib/utils"
import { CompleteTask } from "./CompleteTask"
import { describeRecurrence } from "./recurrence"

interface ColumnOptions {
  /**
   * Show the tasks without any way to change them: an archived project's tasks
   * are read-only until it is unarchived (FR-05.12).
   */
  readOnly?: boolean
}

export function getColumns(
  projectNames: Record<string, string>,
  _depths: Record<string, number>,
  { readOnly = false }: ColumnOptions = {},
): ColumnDef<DataTableFeatures, TaskPublic>[] {
  const columns: ColumnDef<DataTableFeatures, TaskPublic>[] = [
    {
      id: "completed",
      header: () => <span className="sr-only">Completed</span>,
      cell: ({ row }) =>
        readOnly ? (
          <Checkbox
            checked={row.original.completed}
            disabled
            aria-label={row.original.completed ? "Completed" : "Not completed"}
          />
        ) : (
          <CompleteTask task={row.original} />
        ),
    },
    {
      accessorKey: "title",
      header: "Title",
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
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
              row.original.completed && "line-through text-muted-foreground",
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
            {dueDate || "No due date"}
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
          <Badge variant="outline">{priority}</Badge>
        ) : (
          <span className="text-muted-foreground italic">No priority</span>
        )
      },
    },
  ]

  // No row menu: editing, adding a subtask and deleting all live in the task's
  // detail panel, which the row opens. One place to act on a task beats the
  // same three items repeated on every line.
  return columns
}
