import type { ColumnDef } from "@tanstack/react-table"

import type { ProjectPublic } from "@/client"
import type { DataTableFeatures } from "@/components/Common/DataTable"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { ProjectActionsMenu } from "./ProjectActionsMenu"

export const columns: ColumnDef<DataTableFeatures, ProjectPublic>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => (
      <div className="flex items-center gap-2">
        <span className="font-medium">{row.original.name}</span>
        {row.original.is_inbox && (
          <Badge variant="outline" className="text-xs">
            Inbox
          </Badge>
        )}
      </div>
    ),
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
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <ProjectActionsMenu project={row.original} />
      </div>
    ),
  },
]
