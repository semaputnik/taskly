import { useSuspenseQuery } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import { ArrowRight, Bot } from "lucide-react"

import { ActivityService } from "@/client"
import { ActivityDescription } from "@/components/Activity/ActivityDescription"
import { ActorLabel } from "@/components/Activity/ActorLabel"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"
import { cn } from "@/lib/utils"
import { timeAgo } from "./when"

const PREVIEW_ROWS = 6

export const recentActivityQueryOptions = {
  queryKey: ["activity", { skip: 0, limit: PREVIEW_ROWS }],
  queryFn: async () =>
    (
      await ActivityService.readActivityLog({
        query: { skip: 0, limit: PREVIEW_ROWS },
      })
    ).data,
}

function Header() {
  return (
    <h2 className="bg-muted/50 border-b px-4 py-2.5 text-xs font-semibold tracking-wider uppercase">
      While you were away
    </h2>
  )
}

/** The card while its entries are on their way. */
export function WhileYouWereAwayPending() {
  return (
    <div className="bg-card overflow-hidden rounded-lg border">
      <Header />
      {Array.from({ length: 3 }).map((_, index) => (
        <div key={index} className="flex flex-col gap-2 border-b px-4 py-3">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-4 w-44" />
        </div>
      ))}
    </div>
  )
}

/**
 * The account's recent history, newest first. A person and their bots work on
 * the same tasks, so the actor is the first thing each line answers — an entry
 * a bot wrote is news, one the reader wrote themselves is a reminder.
 */
export function WhileYouWereAway() {
  const { user: currentUser } = useAuth()
  const { data } = useSuspenseQuery(recentActivityQueryOptions)
  const entries = data.data

  return (
    <div className="bg-card overflow-hidden rounded-lg border">
      <Header />

      {entries.length === 0 ? (
        <div className="flex flex-col items-center gap-2 px-6 py-12 text-center">
          <Bot className="text-muted-foreground size-6" aria-hidden />
          <p className="font-medium">Nothing has happened yet</p>
          <p className="text-muted-foreground text-sm">
            Every change lands here — including the ones your bot users make
            through the API.
          </p>
          <RouterLink
            to="/bots"
            className="text-link mt-1 text-sm underline-offset-4 hover:underline"
          >
            Connect a bot user
          </RouterLink>
        </div>
      ) : (
        entries.map((entry) => {
          const byBot = Boolean(entry.actor_bot_user_id)
          return (
            <article
              key={entry.id}
              className="flex flex-col gap-1 border-b px-4 py-3 last:border-b-0"
            >
              <div className="flex items-baseline justify-between gap-2">
                <span
                  className={cn(
                    "truncate text-sm",
                    byBot ? "font-medium" : "text-muted-foreground",
                  )}
                >
                  <ActorLabel
                    entry={entry}
                    currentUserId={currentUser?.id}
                    showBadge={false}
                  />
                </span>
                {entry.created_at && (
                  <time
                    dateTime={entry.created_at}
                    className="text-muted-foreground shrink-0 text-xs whitespace-nowrap"
                  >
                    {timeAgo(entry.created_at)}
                  </time>
                )}
              </div>
              <p
                className={cn(
                  "text-sm",
                  byBot ? "text-foreground" : "text-muted-foreground",
                )}
              >
                <ActivityDescription
                  entry={entry}
                  currentUserId={currentUser?.id}
                />
              </p>
            </article>
          )
        })
      )}

      {entries.length > 0 && (
        <RouterLink
          to="/activity"
          className="hover:bg-muted/50 flex items-center justify-between gap-2 border-t px-4 py-3 text-sm transition-colors"
        >
          <span className="text-muted-foreground">See the full log</span>
          <ArrowRight className="text-muted-foreground size-4" aria-hidden />
        </RouterLink>
      )}
    </div>
  )
}
