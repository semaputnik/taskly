import type { ColumnDef } from "@tanstack/react-table"

import type { ProjectPublic } from "@/client"
import type { DataTableFeatures } from "@/components/Common/DataTable"
import { taskCountLabel } from "@/components/Tags/counts"
import { cn } from "@/lib/utils"

export const columns: ColumnDef<DataTableFeatures, ProjectPublic>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
  },
  {
    accessorKey: "description",
    header: "Description",
    cell: ({ row }) => {
      const description = row.original.description
      return (
        <span className={cn("text-muted-foreground", !description && "italic")}>
          {description || "No description"}
        </span>
      )
    },
  },
  {
    id: "tasks",
    header: "Tasks",
    cell: ({ row }) => {
      const count = row.original.task_count ?? 0
      return (
        <span
          className={cn(
            "tabular-nums",
            !count && "text-muted-foreground italic",
          )}
        >
          {count === 0 ? "No tasks" : taskCountLabel(count)}
        </span>
      )
    },
  },
]
