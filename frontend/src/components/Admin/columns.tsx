import type { ColumnDef } from "@tanstack/react-table"

import type { UserPublic } from "@/client"
import { IssueRecoveryCode } from "@/components/Admin/IssueRecoveryCode"
import type { DataTableFeatures } from "@/components/Common/DataTable"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

export type UserTableData = UserPublic & {
  isCurrentUser: boolean
}

/**
 * The registered accounts. Listing them and issuing a recovery code to
 * someone who lost every passkey are the whole of what a superuser can do
 * with other people's accounts (FR-09.2, FR-09.3, FR-12.16).
 */
export const columns: ColumnDef<DataTableFeatures, UserTableData>[] = [
  {
    accessorKey: "full_name",
    header: "Full Name",
    cell: ({ row }) => {
      const fullName = row.original.full_name
      return (
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "font-medium",
              !fullName && "text-muted-foreground font-normal italic",
            )}
          >
            {fullName || "Not set"}
          </span>
          {row.original.isCurrentUser && (
            <Badge variant="outline" className="text-xs">
              You
            </Badge>
          )}
        </div>
      )
    },
  },
  {
    accessorKey: "email",
    header: "Email",
    cell: ({ row }) => (
      <span className="text-muted-foreground">{row.original.email}</span>
    ),
  },
  {
    accessorKey: "is_superuser",
    header: "Role",
    cell: ({ row }) => (
      <Badge variant={row.original.is_superuser ? "default" : "secondary"}>
        {row.original.is_superuser ? "Superuser" : "User"}
      </Badge>
    ),
  },
  {
    accessorKey: "is_active",
    header: "Status",
    cell: ({ row }) => (
      // Status is said in neutrals and shape, never a second hue: a filled
      // dot for an account in use, a hollow one for one that is not.
      <div className="flex items-center gap-2">
        <span
          aria-hidden
          className={cn(
            "size-2 rounded-full border",
            row.original.is_active
              ? "border-foreground bg-foreground"
              : "border-muted-foreground",
          )}
        />
        <span className={row.original.is_active ? "" : "text-muted-foreground"}>
          {row.original.is_active ? "Active" : "Inactive"}
        </span>
      </div>
    ),
  },
  {
    id: "recovery",
    header: () => <span className="sr-only">Recovery</span>,
    cell: ({ row }) =>
      // The superuser's own code comes from the server's command line
      // (FR-12.19).
      row.original.isCurrentUser ? null : (
        <div className="flex justify-end">
          <IssueRecoveryCode user={row.original} />
        </div>
      ),
  },
]
