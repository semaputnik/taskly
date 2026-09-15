import type { ColumnDef } from "@tanstack/react-table"

import type { ProjectPublic } from "@/client"
import type { DataTableFeatures } from "@/components/Common/DataTable"
import { cn } from "@/lib/utils"
import UnarchiveProject from "./UnarchiveProject"

/**
 * Archived projects offer one action only: unarchiving. Everything else about
 * them is frozen until then (FR-05.12).
 */
export const archivedColumns: ColumnDef<DataTableFeatures, ProjectPublic>[] = [
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
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <UnarchiveProject project={row.original} />
      </div>
    ),
  },
]
