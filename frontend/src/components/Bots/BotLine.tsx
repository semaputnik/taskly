import { Link as RouterLink } from "@tanstack/react-router"

import type { BotUserPublic } from "@/client"
import { recordLink, useIsOpen } from "@/components/Records/panels"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import { tokenStatus } from "./tokens"
import { deliveryFailing, webhookStateInWords } from "./webhookWords"
import {
  deletedInWords,
  lastUseInWords,
  monogram,
  permissionsInWords,
  projectsInWords,
  stillNamedInWords,
  TOKEN_WORDS,
} from "./words"

type Projects = Record<string, { name: string; archived: boolean }>

/**
 * The bot user's mark: two letters on a small plate, in ink while its token
 * works and in grey when it does not, so a list of them says which are alive
 * before a word is read.
 */
export function BotPlate({
  name,
  off = false,
  className,
}: {
  name: string
  /** Set for a bot user that is not working: no token, or a deleted one. */
  off?: boolean
  className?: string
}) {
  return (
    <span
      aria-hidden
      className={cn(
        "grid size-[26px] shrink-0 place-items-center rounded-md font-mono text-[11px] font-semibold",
        off ? "bg-rule-strong text-ink-2" : "bg-ink text-page",
        className,
      )}
    >
      {monogram(name)}
    </span>
  )
}

/**
 * A bot user as a line: its plate, its name, and beneath the name what it is
 * in words — whether its token works, which projects it reaches, what it may
 * do — with when it was last heard from at the right.
 *
 * The name opens the column, as a task's title does, rather than the whole
 * line: the same rule, so a list of records behaves as one.
 */
export function BotLine({
  bot,
  projects,
}: {
  bot: BotUserPublic
  projects: Projects
}) {
  const open = useIsOpen("bot", bot.id)
  const status = bot.deleted ? null : tokenStatus(bot)
  const working = status === "active"
  const webhookState = webhookStateInWords(bot.webhooks)
  const failing = deliveryFailing(bot.webhooks)

  return (
    <li
      className={cn(
        "border-rule hover:row-tint grid grid-cols-[26px_minmax(0,1fr)_auto] items-start gap-x-3 border-b py-2.5 transition-colors last:border-b-0",
        open && "row-tint",
      )}
    >
      <BotPlate name={bot.name} off={!working} className="mt-px" />
      <div className="min-w-0">
        <RouterLink
          {...recordLink("bot", bot.id)}
          className={cn(
            "focus-visible:ring-ring/50 block truncate rounded-sm leading-snug font-medium underline-offset-4 outline-none hover:underline focus-visible:ring-[3px]",
            bot.deleted && "text-ink-3",
          )}
        >
          {bot.name}
        </RouterLink>
        <div className="text-ink-3 mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.8125rem] leading-tight">
          {bot.deleted ? (
            <>
              <span>{deletedInWords(bot.deleted_at)}</span>
              <span>{stillNamedInWords(bot.assigned_task_count ?? 0)}</span>
            </>
          ) : (
            <>
              <span className="flex items-center gap-1.5">
                <span
                  aria-hidden
                  className={cn(
                    "size-[7px] shrink-0 rounded-full",
                    working ? "bg-done" : "border-ink-3 border-[1.5px]",
                  )}
                />
                <span className={cn(working && "text-ink-2 font-medium")}>
                  {TOKEN_WORDS[status ?? "none"]}
                </span>
              </span>
              <span>
                <span className="sr-only">Projects: </span>
                {projectsInWords(bot.scope.project_ids, projects)}
              </span>
              <span>
                <span className="sr-only">Permissions: </span>
                {permissionsInWords(bot.scope.permissions)}
              </span>
              {webhookState && <span>{webhookState}</span>}
              {failing && (
                <span className="text-late font-medium">
                  last delivery failed
                </span>
              )}
              {/* On a phone the right-hand column would take a third of the
                  line, so last use joins the facts instead. */}
              <span className="sm:hidden">{lastUseInWords(bot)}</span>
            </>
          )}
        </div>
      </div>
      {!bot.deleted && (
        <span className="text-ink-3 hidden text-right text-[0.8125rem] leading-snug whitespace-nowrap sm:block">
          {lastUseInWords(bot)}
        </span>
      )}
    </li>
  )
}

/** A line while its bot user is on its way: the same two lines, in outline. */
export function BotLinePending() {
  return (
    <div className="border-rule grid grid-cols-[26px_minmax(0,1fr)_auto] gap-x-3 border-b py-2.5 last:border-b-0">
      <Skeleton className="size-[26px] rounded-md" />
      <div className="flex flex-col gap-1.5">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-3 w-56 max-w-full" />
      </div>
      <Skeleton className="h-3 w-20" />
    </div>
  )
}
