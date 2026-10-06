import { useMutation, useQuery } from "@tanstack/react-query"
import { useEffect, useState } from "react"

import { type BotScope, BotsService, type BotUserPublic } from "@/client"
import { useRecordPanel } from "@/components/Records/panels"
import {
  EditableText,
  gutter,
  PropertyList,
  PropertyRow,
  RecordPanel,
  titleFieldClass,
} from "@/components/Records/RecordPanel"
import { useWalk } from "@/components/Records/walk"
import { formatDateTime, formatDayOf } from "@/lib/dates"
import { scopeProjectsQuery, useReportChange } from "@/lib/serverState"
import { toastError } from "@/lib/toasts"
import { cn } from "@/lib/utils"
import { BotPlate } from "./BotLine"
import { BotActivity, OnItsPlate } from "./BotWork"
import DeleteBotUser from "./DeleteBotUser"
import { ago } from "./health"
import IssueToken from "./IssueToken"
import { NewBotUser } from "./NewBotUser"
import RevokeToken from "./RevokeToken"
import { PermissionsSection, ProjectsSection } from "./ScopeSections"
import { tokenStatus } from "./tokens"
import { reachInWords } from "./words"

/**
 * A bot user as one document: what it is, what it may reach and do, and the
 * one credential that lets it in, then what it is on and what it has done.
 *
 * There are no tabs. The column reads top to bottom like a task's does — the
 * name in place, a property list, then sections under hairline headings — and
 * every change saves as it is made, with no Save anywhere (FR-08.9).
 */
export function BotPanel() {
  const { id, capturing, record: bot, panels, shell } = useRecordPanel("bot")
  // The bot users listed on the page behind, so ↓ and ↑ walk them.
  const walk = useWalk(id)

  return (
    <RecordPanel
      {...shell}
      walk={walk}
      onWalk={(to) => panels.walkTo(to, "bot")}
      destructive={
        bot && !bot.deleted && !capturing ? (
          <DeleteBotUser bot={bot} onSuccess={shell.onClose} />
        ) : undefined
      }
      bar={
        capturing ? (
          <>
            <span className="shrink-0">New bot user</span>
            <span aria-hidden>·</span>
            <span className="truncate">Not saved yet</span>
          </>
        ) : bot ? (
          <>
            <span className="shrink-0">Bot user</span>
            {bot.deleted && (
              <>
                <span aria-hidden>·</span>
                <span className="shrink-0">Deleted</span>
              </>
            )}
            {bot.created_at && (
              <>
                <span aria-hidden>·</span>
                <span className="truncate">
                  created {formatDayOf(bot.created_at)}
                </span>
              </>
            )}
          </>
        ) : undefined
      }
    >
      {capturing ? <NewBotUser /> : bot ? <BotRecord bot={bot} /> : null}
    </RecordPanel>
  )
}

function BotRecord({ bot }: { bot: BotUserPublic }) {
  const save = useBotUpdate(bot)
  const status = tokenStatus(bot)

  // Live projects and the archived ones this bot is already scoped to: an
  // archived project stays in a scope, out of reach until it comes back, and
  // a grant the user cannot see is a grant they cannot take away (FR-05.13).
  const { data: projects } = useQuery(scopeProjectsQuery())

  // The scope as the reader has it, which is ahead of the server while a
  // save is in flight. Building each change from the server's copy would let
  // a second tick land before the first came back and quietly undo it.
  const [scope, setScope] = useState(bot.scope)
  // React Query keeps the identity of data that did not change, so this
  // follows the server without undoing an edit that has not landed yet.
  useEffect(() => setScope(bot.scope), [bot.scope])

  const change = async (next: BotScope) => {
    const previous = scope
    setScope(next)
    const saved = await save(next)
    // A refused save leaves the box as the server holds it: the toast says
    // what went wrong, and a box that stayed ticked would say it was granted.
    if (!saved) setScope((current) => (current === next ? previous : current))
  }

  const reach = reachInWords(
    bot,
    Object.fromEntries(
      (projects ?? []).map((project) => [project.id, project]),
    ),
  )

  return (
    <>
      <div
        className={cn(
          "grid grid-cols-[28px_minmax(0,1fr)] items-center gap-3 pt-2 pb-[18px]",
          gutter,
        )}
      >
        <BotPlate
          name={bot.name}
          off={bot.deleted || status !== "active"}
          className="size-7 text-xs"
        />
        {
          // A deleted bot user is kept so that what it did still names it
          // (FR-08.19). Nothing about it changes again, so its name is prose.
          bot.deleted ? (
            <p className="px-2 py-1.5 -ml-2 text-xl leading-snug font-semibold">
              {bot.name}
            </p>
          ) : (
            <EditableText
              value={bot.name}
              ariaLabel="Bot name"
              onCommit={async (name) =>
                name.trim() ? save(undefined, name.trim()) : false
              }
              className={cn(titleFieldClass, "-ml-2")}
            />
          )
        }
      </div>

      {bot.deleted && (
        <p className="text-ink-3 px-4 pb-4 text-sm text-pretty md:px-9">
          This bot user was deleted, and deleting cannot be undone. Its token
          stopped working at once, it takes no new tasks, and everything below —
          what it did and what it was assigned — still names it.
        </p>
      )}

      <PropertyList>
        {bot.deleted ? null : (
          <PropertyRow label="Token">
            <div className="flex flex-wrap items-center gap-x-3.5 gap-y-1">
              <TokenState bot={bot} />
              {/* Issuing keeps its dialog: the token is shown once and cannot
                  be read back, so it is a deliberate step, not a click
                  (FR-08.13). */}
              {bot.has_token ? (
                <RevokeToken bot={bot} />
              ) : (
                <IssueToken bot={bot} />
              )}
            </div>
          </PropertyRow>
        )}

        <PropertyRow label="Last used">
          {/* An empty timestamp and a never-used integration are different
              facts, so the second one is said in words. */}
          <span className="text-ink-2 text-sm">
            {bot.token_last_used_at
              ? `${ago(bot.token_last_used_at)} · ${formatDateTime(bot.token_last_used_at)}`
              : "Never used"}
          </span>
        </PropertyRow>

        <PropertyRow label="Reach">
          <span className="text-ink-2 py-1 text-sm text-pretty">{reach}</span>
        </PropertyRow>
      </PropertyList>

      {/* A deleted bot user reaches nothing and is changed by nothing: its
          reach is the sentence above, and there is nothing to tick. */}
      {bot.deleted ? null : (
        <>
          <ProjectsSection
            idPrefix={`scope-${bot.id}`}
            projects={projects ?? []}
            selected={scope.project_ids}
            onToggle={(projectId, granted) =>
              change({
                ...scope,
                project_ids: granted
                  ? [...scope.project_ids, projectId]
                  : scope.project_ids.filter((id) => id !== projectId),
              })
            }
          />
          <PermissionsSection
            idPrefix={`scope-${bot.id}`}
            permissions={scope.permissions}
            onToggle={(key, granted) =>
              change({
                ...scope,
                permissions: { ...scope.permissions, [key]: granted },
              })
            }
          />
        </>
      )}

      {/* WEBHOOKS SLOT (#191): the Webhooks section goes here, between
          Permissions and On its plate — each of the two webhooks with its URL,
          its last delivery, Send a test, Change and Clear, and Regenerate
          secret at the heading. */}

      <OnItsPlate key={`plate-${bot.id}`} bot={bot} />
      <BotActivity key={`activity-${bot.id}`} bot={bot} />
    </>
  )
}

/** Where the token stands, in the words the integration lives by. */
function TokenState({ bot }: { bot: BotUserPublic }) {
  const status = tokenStatus(bot)
  const quiet = "text-ink-2 text-sm"

  if (status === "active") {
    return (
      <>
        <span className="text-done font-medium">Working</span>
        <span className={quiet}>
          {bot.token_expires_at
            ? `expires ${formatDayOf(bot.token_expires_at)}`
            : "never expires"}
        </span>
      </>
    )
  }
  if (status === "expired") {
    return (
      <>
        <span className="text-late font-medium">Expired</span>
        <span className={quiet}>its requests are refused</span>
      </>
    )
  }
  if (status === "revoked") {
    return (
      <>
        <span className="font-medium">Revoked</span>
        <span className={quiet}>its requests are refused</span>
      </>
    )
  }
  return (
    <>
      <span className="font-medium">No token</span>
      <span className={quiet}>it cannot reach the API</span>
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
  const reportChange = useReportChange()

  const mutation = useMutation({
    mutationFn: ({ scope, name }: { scope?: BotScope; name?: string }) =>
      BotsService.updateBotUser({
        path: { bot_user_id: bot.id },
        body: { scope, name },
      }),
    onError: (error) => toastError(error),
    // A renamed bot user is named on its tasks and in the log.
    onSettled: () => reportChange({ type: "bot user changed", botId: bot.id }),
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
