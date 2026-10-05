import { useSuspenseQuery } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"

import type { ActivityEntryPublic } from "@/client"
import { ActivityDescription } from "@/components/Activity/ActivityDescription"
import { useRestoreDeletion } from "@/components/Activity/RestoreDeletion"
import { recordLink } from "@/components/Records/panels"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"
import { formatDateTime } from "@/lib/dates"
import { activityQuery } from "@/lib/serverState"
import { cn } from "@/lib/utils"
import { byDay, clock, windowLabel } from "./log"

/** How many lines the day page shows before handing off to the full log. */
const LOG_LINES = 8

/** The account's changes in the window the page counts from, newest first. */
export const changesQuery = (since: string | null) =>
  activityQuery({ since: since ?? undefined, limit: LOG_LINES })

const textLink =
  "focus-visible:ring-ring/50 rounded-sm underline-offset-[3px] outline-none hover:underline focus-visible:ring-[3px]"

// The time in a narrow column, the actor, then the sentence. On a phone the
// sentence drops beneath the time and the actor rather than squeezing them.
const line =
  "border-rule grid grid-cols-[8ch_minmax(0,1fr)] items-baseline gap-x-3 gap-y-0.5 border-b py-2 md:grid-cols-[8ch_128px_minmax(0,1fr)]"

function Heading({ count, window }: { count: number | null; window: string }) {
  return (
    <h2 className="border-rule-strong flex items-baseline gap-2 border-b pb-2 text-[13px] font-semibold">
      Changes
      {count !== null && (
        <span className="text-ink-3 font-mono text-xs font-normal">
          {count}
        </span>
      )}
      <span className="text-ink-3 ml-auto font-normal">{window}</span>
    </h2>
  )
}

/** The log while it is on its way: the same heading and line shape. */
export function ChangesPending() {
  return (
    <section className="mb-9">
      <Heading count={null} window="" />
      {Array.from({ length: 3 }).map((_, index) => (
        <div key={index} className={line}>
          <Skeleton className="h-3 w-10" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="col-start-2 h-4 w-56 max-w-full md:col-start-3" />
        </div>
      ))}
    </section>
  )
}

/**
 * The last section of the day page: the account's changes since the reader's
 * last visit, as log lines, newest first. A person and their bot users work
 * on the same tasks, so the actor is the first thing each line says — and a
 * line a bot user wrote is set in full ink, because it is news, while one the
 * reader wrote themselves is muted, because it is a reminder.
 */
export function Changes({ since }: { since: string | null }) {
  const { user } = useAuth()
  const { data } = useSuspenseQuery(changesQuery(since))
  const now = new Date()
  const window = windowLabel(since ? new Date(since) : null, now)

  return (
    <section className="mb-9">
      <Heading count={data.count} window={window} />
      {data.data.length === 0 ? (
        <Empty window={since ? window : null} />
      ) : (
        <>
          {byDay(data.data, now).map((day) => (
            <div key={day.entries[0].id}>
              {day.label && (
                <h3 className="text-ink-3 pt-4 pb-1 text-[13px] font-medium">
                  {day.label}
                </h3>
              )}
              <ol>
                {day.entries.map((entry) => (
                  <Line key={entry.id} entry={entry} currentUserId={user?.id} />
                ))}
              </ol>
            </div>
          ))}
          <RouterLink
            to="/activity"
            className={cn(textLink, "text-ink-3 inline-block pt-2 text-[13px]")}
          >
            Full log <span aria-hidden>→</span>
          </RouterLink>
        </>
      )}
    </section>
  )
}

function Line({
  entry,
  currentUserId,
}: {
  entry: ActivityEntryPublic
  currentUserId?: string
}) {
  const byBot = Boolean(entry.actor_bot_user_id)
  const at = entry.created_at ? new Date(entry.created_at) : null

  return (
    <li className={line}>
      {at ? (
        <time
          dateTime={entry.created_at ?? undefined}
          title={formatDateTime(entry.created_at as string)}
          className="text-ink-3 font-mono text-xs tabular-nums"
        >
          {clock(at)}
        </time>
      ) : (
        <span />
      )}
      <span
        className={cn(
          "truncate",
          byBot ? "text-ink font-medium" : "text-ink-3",
        )}
      >
        {entry.actor_bot_user_id ? (
          <RouterLink
            {...recordLink("bot", entry.actor_bot_user_id)}
            className={textLink}
          >
            {entry.actor_bot_user_name ?? "A bot user"}
          </RouterLink>
        ) : entry.actor_id === currentUserId ? (
          "You"
        ) : (
          "Someone else"
        )}
      </span>
      {/* The sentence follows its actor, so its verb is not capitalised:
          "release-bot deleted …". The words themselves are the full log's. */}
      <span
        className={cn(
          "col-start-2 break-words first-letter:lowercase md:col-start-3",
          byBot ? "text-ink" : "text-ink-3",
        )}
      >
        <ActivityDescription entry={entry} currentUserId={currentUserId} />
        {entry.restorable && <Restore entry={entry} />}
      </span>
    </li>
  )
}

/** Restore, inline after the deletion it undoes: nothing is lost by it. */
function Restore({ entry }: { entry: ActivityEntryPublic }) {
  const { name, mutation } = useRestoreDeletion(entry)
  return (
    <button
      type="button"
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
      aria-label={`Restore ${name}`}
      className={cn(
        textLink,
        "text-ink decoration-rule-strong ml-2.5 text-[13px] underline hover:decoration-current disabled:opacity-60",
      )}
    >
      {mutation.isPending ? "Restoring…" : "Restore"}
    </button>
  )
}

/**
 * Nothing in the window: said in a sentence, pointing at the bot users whose
 * changes land here.
 */
function Empty({ window }: { window: string | null }) {
  return (
    <p className="text-ink-2 pt-3">
      {window ? `Nothing has changed ${window}.` : "Nothing has happened yet."}{" "}
      The changes your{" "}
      <RouterLink
        to="/bots"
        className={cn(
          textLink,
          "text-ink decoration-rule-strong underline hover:decoration-current",
        )}
      >
        bot users
      </RouterLink>{" "}
      make through the API land here, newest first.
    </p>
  )
}
