import { Link } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"

import type { TagPublic } from "@/client"
import type { DataTableFeatures } from "@/components/Common/DataTable"
import { archivedNote, tasks } from "./counts"

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
      const archived = archivedNote(row.original)
      return (
        <span className="flex flex-wrap items-baseline gap-x-2">
          {count === 0 ? (
            <span className="text-muted-foreground">No tasks</span>
          ) : (
            <Link
              to="/tasks"
              search={{ tag: row.original.name }}
              className="underline-offset-4 hover:underline"
            >
              {tasks(count)}
            </Link>
          )}
          {archived && (
            <span className="text-muted-foreground text-xs">{archived}</span>
          )}
        </span>
      )
    },
  },
]
