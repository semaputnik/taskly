import type { ActivityEntryPublic } from "@/client"
import { textLink } from "@/components/Dashboard/shared"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDateTime, formatTimeOf } from "@/lib/dates"
import { cn } from "@/lib/utils"
import { ActivityDescription } from "./ActivityDescription"
import { ActorLabel } from "./ActorLabel"
import { RestoreDeletion } from "./RestoreDeletion"
import { type LogDay, logDays } from "./words"

// The time in a narrow column, the actor, the sentence, and Restore at the
// right. On a phone the sentence drops beneath the time and the actor, and
// Restore beneath the sentence, rather than squeezing them.
const lineGrid =
  "border-rule grid grid-cols-[3.25rem_minmax(0,1fr)] items-baseline gap-x-3 gap-y-0.5 border-b py-[9px] md:grid-cols-[3.25rem_136px_minmax(0,1fr)_auto]"

/**
 * The log in day groups, each with its name and how many lines it holds on
 * this page. A bot user's line is in full ink, because it is news; the
 * reader's own is muted, because it is a reminder.
 */
export function ActivityLog({
  entries,
  currentUserId,
  deletedBotIds,
  now = new Date(),
}: {
  entries: ActivityEntryPublic[]
  currentUserId?: string
  /** The bot users that were deleted, whose names are struck through. */
  deletedBotIds: ReadonlySet<string>
  now?: Date
}) {
  return (
    <div>
      {logDays(entries, now).map((day) => (
        <Day
          key={day.entries[0].id}
          day={day}
          currentUserId={currentUserId}
          deletedBotIds={deletedBotIds}
        />
      ))}
    </div>
  )
}

function Day({
  day,
  currentUserId,
  deletedBotIds,
}: {
  day: LogDay
  currentUserId?: string
  deletedBotIds: ReadonlySet<string>
}) {
  return (
    <section>
      <h2 className="border-rule-strong flex items-baseline gap-2 border-b pt-[22px] pb-1.5 text-[13px] font-semibold">
        {day.heading}
        <span className="text-ink-3 font-mono text-xs font-normal tabular-nums">
          {day.entries.length}
        </span>
      </h2>
      <ol>
        {day.entries.map((entry) => (
          <Line
            key={entry.id}
            entry={entry}
            currentUserId={currentUserId}
            deletedBotIds={deletedBotIds}
          />
        ))}
      </ol>
    </section>
  )
}

function Line({
  entry,
  currentUserId,
  deletedBotIds,
}: {
  entry: ActivityEntryPublic
  currentUserId?: string
  deletedBotIds: ReadonlySet<string>
}) {
  const bot = entry.actor_bot_user_id
  const gone = bot ? deletedBotIds.has(bot) : false

  return (
    <li className={lineGrid}>
      {entry.created_at ? (
        <time
          dateTime={entry.created_at}
          title={formatDateTime(entry.created_at)}
          className="text-ink-3 font-mono text-xs tabular-nums"
        >
          {formatTimeOf(entry.created_at)}
        </time>
      ) : (
        <span />
      )}
      <span
        className={cn("truncate", bot ? "text-ink font-medium" : "text-ink-3")}
      >
        <ActorLabel
          entry={entry}
          currentUserId={currentUserId}
          deleted={gone}
          showBadge={false}
          showIcon={false}
        />
        {bot && <span className="sr-only">, bot user</span>}
      </span>
      {/* The sentence follows its actor, so its verb is not capitalised:
          "release-bot deleted …". The words are the ones the day page and the
          bot user's column use. */}
      <span
        className={cn(
          "col-start-2 break-words first-letter:lowercase md:col-start-3",
          bot ? "text-ink" : "text-ink-3",
        )}
      >
        <ActivityDescription entry={entry} currentUserId={currentUserId} />
      </span>
      {entry.restorable && (
        <span className="col-start-2 text-[13px] md:col-start-4">
          <RestoreDeletion entry={entry} />
        </span>
      )}
    </li>
  )
}

/** The log while it is on its way: the same day heading and line shape. */
export function ActivityLogPending() {
  return (
    <div aria-hidden>
      <div className="border-rule-strong border-b pt-[22px] pb-1.5">
        <Skeleton className="h-3.5 w-16" />
      </div>
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className={lineGrid}>
          <Skeleton className="h-3 w-10" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="col-start-2 h-4 w-64 max-w-full md:col-start-3" />
        </div>
      ))}
    </div>
  )
}

/** The pager's two words: a quiet text button, a thumb tall on touch. */
export function PagerButton({
  disabled,
  onClick,
  children,
}: {
  disabled: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        textLink,
        "hover:text-ink focus-visible:text-ink disabled:pointer-events-none disabled:opacity-40 pointer-coarse:-my-3.5 pointer-coarse:px-2 pointer-coarse:py-3.5",
      )}
    >
      {children}
    </button>
  )
}
