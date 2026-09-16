import type { ColumnDef } from "@tanstack/react-table"

import type { BotUserPublic } from "@/client"
import type { DataTableFeatures } from "@/components/Common/DataTable"
import { Badge } from "@/components/ui/badge"
import type { ScopeProject } from "./BotFormFields"
import { liveness, livenessText } from "./health"
import { PERMISSIONS } from "./permissions"
import { tokenStatus } from "./tokens"

// The row says where a token stands; when it was issued, when it expires and
// when it was last used are properties, read in the bot user's panel.
const STATUS_TEXT = {
  none: "No token",
  active: "Active",
  revoked: "Revoked",
  expired: "Expired",
} as const

export function getColumns(
  projects: Record<string, ScopeProject>,
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
            {ids.map((id) => {
              const project = projects[id]
              // An archived project stays in the scope, but no bot user
              // reaches it while it is archived.
              return (
                <Badge
                  key={id}
                  variant="outline"
                  className={project?.archived ? "text-muted-foreground" : ""}
                >
                  {project
                    ? `${project.name}${project.archived ? " (archived)" : ""}`
                    : "Unavailable project"}
                </Badge>
              )
            })}
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
        const status = tokenStatus(row.original)
        return status === "expired" ? (
          <Badge variant="destructive">Expired</Badge>
        ) : (
          <span
            className={
              status === "active" ? undefined : "text-muted-foreground"
            }
          >
            {STATUS_TEXT[status]}
          </span>
        )
      },
    },
    {
      id: "liveness",
      header: "Last used",
      // Whether an integration is alive is the question a list of agents is
      // scanned for. It is said in words and weight rather than in a colour:
      // teal is for action, location and focus, and nothing else.
      cell: ({ row }) => (
        <span
          className={
            liveness(row.original) === "working"
              ? undefined
              : "text-muted-foreground"
          }
        >
          {livenessText(row.original)}
        </span>
      ),
    },
  ]
}
