import type { ColumnDef } from "@tanstack/react-table"

import type { TagPublic } from "@/client"
import type { DataTableFeatures } from "@/components/Common/DataTable"
import { BotCreator } from "./BotCreator"
import { TaskCount } from "./TaskCount"

export const columns: ColumnDef<DataTableFeatures, TagPublic>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => (
      <span className="flex flex-wrap items-center gap-2">
        <span className="font-medium whitespace-pre">{row.original.name}</span>
        <BotCreator tag={row.original} />
      </span>
    ),
  },
  {
    id: "tasks",
    header: "Tasks",
    cell: ({ row }) => <TaskCount tag={row.original} />,
  },
]
