import { Link } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"

import type { TagPublic } from "@/client"
import type { DataTableFeatures } from "@/components/Common/DataTable"

export const columns: ColumnDef<DataTableFeatures, TagPublic>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
  },
  {
    id: "tasks",
    header: "Tasks",
    cell: ({ row }) => {
      const count = row.original.task_count ?? 0
      if (count === 0) {
        return <span className="text-muted-foreground">No tasks</span>
      }
      return (
        <Link
          to="/tasks"
          search={{ tag: row.original.name }}
          className="underline-offset-4 hover:underline"
        >
          {count} {count === 1 ? "task" : "tasks"}
        </Link>
      )
    },
  },
]
