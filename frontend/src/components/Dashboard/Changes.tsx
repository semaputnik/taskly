import { useSuspenseQueries } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"

import type { ActivityEntryPublic } from "@/client"
import { ActivityDescription } from "@/components/Activity/ActivityDescription"
import { ActorLabel } from "@/components/Activity/ActorLabel"
import { useRestoreDeletion } from "@/components/Activity/RestoreDeletion"
import { ME } from "@/components/Activity/words"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"
import { formatDateTime } from "@/lib/dates"
import { cn } from "@/lib/utils"
import { byDay, clock, windowLabel } from "./log"
import { botChangesQuery, ownChangesQuery } from "./queries"
import { textLink } from "./shared"

// The time in a narrow column, the actor, then the sentence. On a phone the
// sentence drops beneath the time and the actor rather than squeezing them.
const lineGrid =
  "border-rule grid grid-cols-[8ch_minmax(0,1fr)] items-baseline gap-x-3 gap-y-0.5 border-b py-2 md:grid-cols-[8ch_128px_minmax(0,1fr)]"

// A link inside a sentence has to look like one before it is hovered.
const inlineLink = cn(
  textLink,
  "text-ink decoration-rule-strong underline hover:decoration-current",
)

function Heading({
  count,
  windowText,
}: {
  count: number | null
  windowText: string
}) {
  return (
    <h2 className="border-rule-strong flex items-baseline gap-2 border-b pb-2 text-[13px] font-semibold">
      Changes
      {count !== null && (
        <span className="text-ink-3 font-mono text-xs font-normal">
          {count}
        </span>
      )}
      <span className="text-ink-3 ml-auto font-normal">{windowText}</span>
    </h2>
  )
}

/** The log while it is on its way: the same heading and line shape. */
export function ChangesPending() {
  return (
    <section className="mb-9">
      <Heading count={null} windowText="" />
      {Array.from({ length: 3 }).map((_, index) => (
        <div key={index} className={lineGrid}>
          <Skeleton className="h-3 w-10" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="col-start-2 h-4 w-56 max-w-full md:col-start-3" />
        </div>
      ))}
    </section>
  )
}

/**
 * The last section of the day page: what the reader's bot users changed
 * since their last visit, as log lines, newest first. A person and their bot
 * users work on the same tasks, so the actor is the first thing each line
 * says. The reader's own changes are not listed — they know what they did —
 * but folded into one muted line at the end that opens them in the Activity
 * log, so the section is never a list of the reader's own actions.
 */
export function Changes({ since }: { since: string | null }) {
  const { user } = useAuth()
  const [bots, own] = useSuspenseQueries({
    queries: [botChangesQuery(since), ownChangesQuery(since)],
  })
  const now = new Date()
  const windowText = windowLabel(since ? new Date(since) : null, now)
  const ownCount = own.data.count

  return (
    <section className="mb-9">
      <Heading count={bots.data.count} windowText={windowText} />
      {bots.data.count === 0 && ownCount === 0 ? (
        <Empty windowText={since ? windowText : null} />
      ) : bots.data.data.length === 0 ? (
        <p className="text-ink-3 pt-3">
          Nothing from your bot users {windowText}.{" "}
          <OwnChanges count={ownCount} />
        </p>
      ) : (
        <>
          {byDay(bots.data.data, now).map((day) => (
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
          {ownCount > 0 && (
            <p className="text-ink-3 pt-2.5">
              and <OwnChanges count={ownCount} />
            </p>
          )}
        </>
      )}
      <RouterLink
        to="/activity"
        className={cn(textLink, "text-ink-3 inline-block pt-2 text-[13px]")}
      >
        Full log <span aria-hidden>→</span>
      </RouterLink>
    </section>
  )
}

/** The reader's own changes as one link, into the log narrowed to them. */
function OwnChanges({ count }: { count: number }) {
  return (
    <RouterLink
      to="/activity"
      search={{ actor: ME }}
      className={cn(
        textLink,
        "decoration-rule-strong underline hover:decoration-current",
      )}
    >
      {count} {count === 1 ? "change" : "changes"} of yours{" "}
      <span aria-hidden>→</span>
    </RouterLink>
  )
}

function Line({
  entry,
  currentUserId,
}: {
  entry: ActivityEntryPublic
  currentUserId?: string
}) {
  return (
    <li className={lineGrid}>
      {entry.created_at ? (
        <time
          dateTime={entry.created_at}
          title={formatDateTime(entry.created_at)}
          className="text-ink-3 font-mono text-xs tabular-nums"
        >
          {clock(new Date(entry.created_at))}
        </time>
      ) : (
        <span />
      )}
      <span className="text-ink truncate font-medium">
        <ActorLabel
          entry={entry}
          currentUserId={currentUserId}
          showBadge={false}
          showIcon={false}
        />
      </span>
      {/* The sentence follows its actor, so its verb is not capitalised:
          "release-bot deleted …". The words themselves are the full log's. */}
      <span className="text-ink col-start-2 break-words first-letter:lowercase md:col-start-3">
        <ActivityDescription entry={entry} currentUserId={currentUserId} />
        {entry.restorable && <Restore entry={entry} />}
      </span>
    </li>
  )
}

/**
 * Restore, inline after the deletion it undoes: it loses nothing, so it asks
 * nothing first, and the toast says what came back.
 */
function Restore({ entry }: { entry: ActivityEntryPublic }) {
  const { name, mutation } = useRestoreDeletion(entry)
  return (
    <button
      type="button"
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
      aria-label={`Restore ${name}`}
      className={cn(inlineLink, "ml-2.5 text-[13px] disabled:opacity-60")}
    >
      Restore
    </button>
  )
}

/**
 * Nothing in the window: said in a sentence, pointing at the bot users whose
 * changes land here.
 */
function Empty({ windowText }: { windowText: string | null }) {
  return (
    <p className="text-ink-2 pt-3">
      {windowText
        ? `Nothing has changed ${windowText}.`
        : "Nothing has happened yet."}{" "}
      The changes your{" "}
      <RouterLink to="/bots" className={inlineLink}>
        bot users
      </RouterLink>{" "}
      make through the API land here, newest first.
    </p>
  )
}
