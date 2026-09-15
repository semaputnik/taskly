import type { ColumnDef } from "@tanstack/react-table"

import type { BotUserPublic } from "@/client"
import type { DataTableFeatures } from "@/components/Common/DataTable"
import { Badge } from "@/components/ui/badge"
import { BotActionsMenu } from "./BotActionsMenu"
import type { ScopeProject } from "./BotFormFields"
import IssueToken from "./IssueToken"
import { PERMISSIONS } from "./permissions"
import RevokeToken from "./RevokeToken"
import { formatDate, formatDateTime, tokenStatus } from "./tokens"

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
      cell: ({ row }) => <TokenCell bot={row.original} />,
    },
    {
      id: "actions",
      header: () => <span className="sr-only">Actions</span>,
      cell: ({ row }) => (
        <div className="flex justify-end">
          <BotActionsMenu bot={row.original} />
        </div>
      ),
    },
  ]
}

function TokenCell({ bot }: { bot: BotUserPublic }) {
  const status = tokenStatus(bot)

  if (status === "none" || status === "revoked") {
    return (
      <div className="flex flex-col items-start gap-1.5">
        {status === "revoked" && (
          <span className="text-muted-foreground text-xs">
            Revoked {formatDate(bot.token_revoked_at)}
          </span>
        )}
        <IssueToken bot={bot} />
      </div>
    )
  }

  return (
    <div className="flex flex-col items-start gap-1.5 text-xs">
      {status === "expired" ? (
        <Badge variant="destructive">
          Expired {formatDate(bot.token_expires_at)}
        </Badge>
      ) : (
        <span>
          {bot.token_expires_at
            ? `Expires ${formatDate(bot.token_expires_at)}`
            : "Never expires"}
        </span>
      )}
      <span className="text-muted-foreground">
        {bot.token_last_used_at
          ? `Last used ${formatDateTime(bot.token_last_used_at)}`
          : "Never used"}
      </span>
      <RevokeToken bot={bot} />
    </div>
  )
}
