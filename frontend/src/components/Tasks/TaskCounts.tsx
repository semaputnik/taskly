import { useQueries } from "@tanstack/react-query"

import { Skeleton } from "@/components/ui/skeleton"
import { tasksQuery } from "@/lib/serverState"
import { counts } from "./listWords"
import { OPEN_STATUSES } from "./statuses"

/** One row asked for, so the request is the count and nothing else. */
const COUNT = { skip: 0, limit: 1 } as const

/**
 * The one sentence under the page's heading: how much is open, and of that
 * how much is in Backlog, on bot users, and overdue — real counts, of the
 * whole of the reader's open work rather than of what the filters below have
 * narrowed it to. "Open" is the same count the navigation shows, and shares
 * its request.
 *
 * Nothing is drawn but a line of the sentence's height until all four have
 * come, so the sentence never changes length under the filters.
 */
export function TaskCounts() {
  const [open, backlog, onBots, overdue] = useQueries({
    queries: [
      tasksQuery({ status: OPEN_STATUSES, ...COUNT }),
      tasksQuery({ status: ["backlog"], ...COUNT }),
      tasksQuery({ status: OPEN_STATUSES, assigned_to_bots: true, ...COUNT }),
      tasksQuery({ status: OPEN_STATUSES, overdue: true, ...COUNT }),
    ],
  })

  if (!open.data || !backlog.data || !onBots.data || !overdue.data) {
    // A count that cannot be had leaves the sentence out; the list below says
    // for itself when it cannot be read.
    if ([open, backlog, onBots, overdue].some((query) => query.isError)) {
      return <div className="mb-5" />
    }
    return (
      <div className="mb-5 flex h-[1.45em] items-center">
        <Skeleton className="h-4 w-72 max-w-full" />
      </div>
    )
  }
  const { lead, rest } = counts({
    open: open.data.count,
    backlog: backlog.data.count,
    onBots: onBots.data.count,
    overdue: overdue.data.count,
  })
  return (
    <p className="text-ink-3 mb-5">
      <span className="text-ink font-medium">{lead}</span> {rest}
    </p>
  )
}
