import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Activity,
  CalendarClock,
  Clock,
  FolderKanban,
  KeyRound,
  ShieldCheck,
} from "lucide-react"
import { useEffect, useState } from "react"

import { type BotScope, BotsService, type BotUserPublic } from "@/client"
import {
  EditableText,
  PropertyList,
  PropertyRow,
  ReadOnlyValue,
  RecordHeader,
  RecordPanel,
  recordLoad,
  titleFieldClass,
  valueInset,
} from "@/components/Records/RecordPanel"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import useCustomToast from "@/hooks/useCustomToast"
import { formatDateTime, formatDayOf } from "@/lib/dates"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"
import { BotConsole } from "./BotConsole"
import { scopeProjectsQueryOptions } from "./BotFormFields"
import DeleteBotUser from "./DeleteBotUser"
import { ago, until } from "./health"
import IssueToken from "./IssueToken"
import { PERMISSION_GROUPS } from "./permissions"
import RevokeToken from "./RevokeToken"
import { tokenStatus } from "./tokens"

// What the token state means for the integration, rather than what it is.
const STATUS_TEXT = {
  none: "No token — this bot user cannot reach the API",
  active: "Working",
  revoked: "Revoked — its requests are refused",
  expired: "Expired — its requests are refused",
} as const

/**
 * A bot user as a record: what it may reach, what it may do, and the one
 * credential that lets it in.
 *
 * Its row used to stack token status, last-used text and an action button in
 * one cell, with the rest of its actions in an overflow menu 260 pixels away.
 * Here each of those is a property, read where it is changed.
 */
export function BotPanel({
  botId,
  onClose,
}: {
  botId: string | null
  onClose: () => void
}) {
  const query = useQuery({
    queryKey: ["bot", botId],
    queryFn: async () =>
      (
        await BotsService.readBotUser({
          path: { bot_user_id: botId as string },
        })
      ).data,
    enabled: Boolean(botId),
  })
  const bot = query.data

  return (
    <RecordPanel
      open={Boolean(botId)}
      onClose={onClose}
      name={bot?.name ?? "Bot user"}
      kind="bot user"
      {...recordLoad(query, Boolean(botId))}
      destructive={
        bot && !bot.deleted ? (
          <DeleteBotUser bot={bot} onSuccess={onClose} />
        ) : undefined
      }
    >
      {bot ? <BotRecord bot={bot} /> : null}
    </RecordPanel>
  )
}

function BotRecord({ bot }: { bot: BotUserPublic }) {
  const save = useBotUpdate(bot)
  const status = tokenStatus(bot)

  // Live projects and the archived ones this bot is already scoped to: an
  // archived project stays in a scope, out of reach until it comes back, and
  // a grant the user cannot see is a grant they cannot take away (FR-05.13).
  const { data: projects } = useQuery(scopeProjectsQueryOptions())

  // The scope as the reader has it, which is ahead of the server while a
  // save is in flight. Building each change from the server's copy would let
  // a second tick land before the first came back and quietly undo it.
  const [scope, setScope] = useState(bot.scope)
  // React Query keeps the identity of data that did not change, so this
  // follows the server without undoing an edit that has not landed yet.
  useEffect(() => setScope(bot.scope), [bot.scope])

  const change = (next: BotScope) => {
    setScope(next)
    return save(next)
  }

  const toggleProject = (projectId: string, granted: boolean) => {
    const project_ids = granted
      ? [...scope.project_ids, projectId]
      : scope.project_ids.filter((id) => id !== projectId)
    change({ ...scope, project_ids })
  }

  return (
    <>
      <RecordHeader
        breadcrumb={
          <>
            <span className="shrink-0">Bot user</span>
            {bot.deleted && (
              <>
                <span aria-hidden>·</span>
                <span className="shrink-0">Deleted</span>
              </>
            )}
          </>
        }
        title={
          // A deleted bot user is kept so that what it did still names it
          // (FR-08.19). Nothing about it changes again, so its name is prose.
          bot.deleted ? (
            <p className="px-2 py-1.5 text-xl leading-snug font-semibold">
              {bot.name}
            </p>
          ) : (
            <EditableText
              value={bot.name}
              ariaLabel="Bot name"
              onCommit={async (name) =>
                name.trim() ? save(undefined, name.trim()) : false
              }
              className={titleFieldClass}
            />
          )
        }
      />

      {bot.deleted && (
        <p className="text-muted-foreground border-b px-6 pb-5 text-sm text-pretty">
          This bot user was deleted, and deleting cannot be undone. Its token
          stopped working at once, it takes no new tasks, and everything below —
          what it did and what it was assigned — still names it.
        </p>
      )}

      <PropertyList>
        <PropertyRow icon={KeyRound} label="Token">
          <div className={cn("flex flex-wrap items-center gap-2", valueInset)}>
            <span>{STATUS_TEXT[status]}</span>
            {/* Issuing keeps its dialog: the token is shown once and cannot be
                read back, so it is a deliberate step, not a click (FR-08.13). */}
            {bot.deleted ? null : bot.has_token ? (
              <RevokeToken bot={bot} />
            ) : (
              <IssueToken bot={bot} />
            )}
          </div>
        </PropertyRow>

        <PropertyRow icon={CalendarClock} label="Expires">
          <ReadOnlyValue>
            {/* Only a token that still works has an expiry worth counting
                down to; a revoked one stopped before its date, and an expired
                one is past it. */}
            {!bot.token_expires_at
              ? bot.has_token
                ? "Never — it works until revoked"
                : "—"
              : status === "active"
                ? `${until(bot.token_expires_at)} — ${formatDayOf(bot.token_expires_at)}`
                : formatDayOf(bot.token_expires_at)}
          </ReadOnlyValue>
        </PropertyRow>

        <PropertyRow icon={Activity} label="Last used">
          {/* An empty timestamp and a never-used integration are different
              facts, so the second one is said in words. */}
          <ReadOnlyValue>
            {bot.token_last_used_at ? (
              <>
                {ago(bot.token_last_used_at)}
                <span className="text-xs">
                  {" "}
                  ({formatDateTime(bot.token_last_used_at)})
                </span>
              </>
            ) : (
              "Never used"
            )}
          </ReadOnlyValue>
        </PropertyRow>

        <PropertyRow icon={FolderKanban} label="Projects">
          <div className={cn("flex flex-col gap-2 py-1", valueInset)}>
            {(projects ?? []).map((project) => {
              const id = `scope-${bot.id}-${project.id}`
              return (
                <div key={project.id} className="flex items-center gap-2">
                  <Checkbox
                    id={id}
                    disabled={bot.deleted}
                    checked={scope.project_ids.includes(project.id)}
                    onCheckedChange={(checked) =>
                      toggleProject(project.id, checked === true)
                    }
                  />
                  <Label htmlFor={id} className="font-normal">
                    {project.name}
                    {project.archived && (
                      <span className="text-muted-foreground">(archived)</span>
                    )}
                  </Label>
                </div>
              )
            })}
            {projects?.length === 0 && (
              <ReadOnlyValue>No projects to grant yet</ReadOnlyValue>
            )}
            <p className="text-muted-foreground text-xs text-pretty">
              A bot user reaches only the projects named here, and never an
              archived one.
            </p>
          </div>
        </PropertyRow>

        <PropertyRow icon={ShieldCheck} label="Permissions">
          <div className={cn("flex flex-col gap-3 py-1", valueInset)}>
            {PERMISSION_GROUPS.map((group) => (
              <fieldset key={group.title} className="flex flex-col gap-2">
                <legend className="text-muted-foreground text-xs">
                  {group.title}
                </legend>
                {group.permissions.map(({ key, label }) => {
                  const id = `permission-${bot.id}-${key}`
                  return (
                    <div key={key} className="flex items-center gap-2">
                      <Checkbox
                        id={id}
                        disabled={bot.deleted}
                        checked={Boolean(scope.permissions[key])}
                        onCheckedChange={(checked) =>
                          change({
                            ...scope,
                            permissions: {
                              ...scope.permissions,
                              [key]: checked === true,
                            },
                          })
                        }
                      />
                      <Label htmlFor={id} className="font-normal">
                        {label}
                      </Label>
                    </div>
                  )
                })}
              </fieldset>
            ))}
          </div>
        </PropertyRow>

        <PropertyRow icon={Clock} label="Created">
          <ReadOnlyValue>
            {bot.created_at ? formatDayOf(bot.created_at) : "Unknown"}
          </ReadOnlyValue>
        </PropertyRow>
      </PropertyList>

      <BotConsole bot={bot} />
    </>
  )
}

/**
 * Saving one thing about a bot user.
 *
 * The API takes a scope whole, so a scope change sends the scope the reader
 * is looking at with the one box they ticked already flipped. Nothing is held
 * back: there is no Save button here either (FR-08.9).
 */
function useBotUpdate(bot: BotUserPublic) {
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: ({ scope, name }: { scope?: BotScope; name?: string }) =>
      BotsService.updateBotUser({
        path: { bot_user_id: bot.id },
        body: { scope, name },
      }),
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["bots"] })
      queryClient.invalidateQueries({ queryKey: ["bot", bot.id] })
      // A renamed bot user is named on its tasks and in the log.
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
    },
  })

  return async (scope?: BotScope, name?: string) => {
    try {
      await mutation.mutateAsync({ scope, name })
      return true
    } catch {
      return false
    }
  }
}
