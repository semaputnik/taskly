import type { ColumnDef } from "@tanstack/react-table"

import type { BotUserPublic } from "@/client"
import type { DataTableFeatures } from "@/components/Common/DataTable"
import { Badge } from "@/components/ui/badge"
import IssueToken from "./IssueToken"
import { PERMISSIONS } from "./permissions"

export function getColumns(
  projectNames: Record<string, string>,
): ColumnDef<DataTableFeatures, BotUserPublic>[] {
  return [
    {
      accessorKey: "name",
      header: "Name",
      cell: ({ row }) => (
        <span className="font-medium">{row.original.name}</span>
      ),
    },
    {
      id: "projects",
      header: "Projects",
      cell: ({ row }) => {
        const ids = row.original.scope.project_ids
        if (ids.length === 0) {
          return <span className="text-muted-foreground">None</span>
        }
        return (
          <div className="flex flex-wrap gap-1">
            {ids.map((id) => (
              <Badge key={id} variant="outline">
                {/* A project out of the live list is archived or deleted. */}
                {projectNames[id] ?? "Unavailable project"}
              </Badge>
            ))}
          </div>
        )
      },
    },
    {
      id: "permissions",
      header: "Permissions",
      cell: ({ row }) => {
        const granted = PERMISSIONS.filter(
          ({ key }) => row.original.scope.permissions[key],
        )
        if (granted.length === 0) {
          return <span className="text-muted-foreground">None</span>
        }
        return (
          <div className="flex flex-wrap gap-1">
            {granted.map(({ key, label }) => (
              <Badge key={key} variant="secondary">
                {label}
              </Badge>
            ))}
          </div>
        )
      },
    },
    {
      id: "token",
      header: "Token",
      cell: ({ row }) => {
        const bot = row.original
        if (!bot.has_token) {
          return <IssueToken bot={bot} />
        }
        return (
          <span className="text-muted-foreground">
            Issued{" "}
            {bot.token_issued_at
              ? new Date(bot.token_issued_at).toLocaleDateString()
              : ""}
          </span>
        )
      },
    },
  ]
}
