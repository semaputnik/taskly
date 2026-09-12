import type { ColumnDef } from "@tanstack/react-table"

import type { TaskPublic } from "@/client"
import type { DataTableFeatures } from "@/components/Common/DataTable"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { CompleteTask } from "./CompleteTask"
import { TaskActionsMenu } from "./TaskActionsMenu"

// Each level of nesting shifts a subtask's title right by this much.
const INDENT_PER_LEVEL_REM = 1.25

export function getColumns(
  projectNames: Record<string, string>,
  depths: Record<string, number>,
): ColumnDef<DataTableFeatures, TaskPublic>[] {
  return [
    {
      id: "completed",
      header: () => <span className="sr-only">Completed</span>,
      cell: ({ row }) => <CompleteTask task={row.original} />,
    },
    {
      accessorKey: "title",
      header: "Title",
      cell: ({ row }) => (
        <span
          className={cn(
            "font-medium",
            row.original.completed && "line-through text-muted-foreground",
          )}
          style={{
            paddingLeft: `${(depths[row.original.id] ?? 0) * INDENT_PER_LEVEL_REM}rem`,
          }}
        >
          {row.original.title}
        </span>
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
    {
      id: "actions",
      header: () => <span className="sr-only">Actions</span>,
      cell: ({ row }) => (
        <div className="flex justify-end">
          <TaskActionsMenu task={row.original} />
        </div>
      ),
    },
  ]
}
