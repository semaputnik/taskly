import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useEffect } from "react"

import { ActivityFilters } from "@/components/Activity/ActivityFilters"
import {
  ActivityLog,
  ActivityLogPending,
  PagerButton,
} from "@/components/Activity/ActivityLog"
import {
  activitySearchSchema,
  byBotsQuery,
  everythingQuery,
  logRequest,
  prefetchActivity,
} from "@/components/Activity/queries"
import {
  emptyMessage,
  type LogOrder,
  lede,
  PAGE_SIZE,
  pagerLabels,
  pagerText,
} from "@/components/Activity/words"
import { textLink } from "@/components/Dashboard/shared"
import useAuth from "@/hooks/useAuth"
import { activityQuery, deletedBotsQuery } from "@/lib/serverState"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/_layout/activity")({
  component: Activity,
  validateSearch: activitySearchSchema,
  // The requests start as soon as the route is matched, beside the download
  // of the page's own code rather than after it. Nothing waits on them here,
  // and what is cached is left alone. The address is read as the page will
  // read it, so both ask under the same key.
  loader: ({ context, location }) => {
    const search = activitySearchSchema.safeParse(location.search)
    if (search.success) prefetchActivity(context.queryClient, search.data)
  },
  head: () => ({
    meta: [
      {
        title: "Activity - Taskly",
      },
    ],
  }),
})

/**
 * The user's activity log (FR-10.1), as day groups of lines: when, who, what
 * happened to which record, and Restore where a deletion can be undone. Only
 * ever their own entries: the API offers no way to ask for anyone else's
 * (FR-10.7).
 */
function Activity() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const { user: currentUser } = useAuth()
  const page = search.page ?? 1
  const order: LogOrder = search.order ?? "newest"

  const { data, isPending, isError, refetch } = useQuery(
    activityQuery(logRequest(search)),
  )
  // The sentence counts the whole log. Whether it could be counted is the
  // sentence's affair alone: a count that fails costs it that half.
  const { data: everything } = useQuery(everythingQuery())
  const { data: byBots } = useQuery(byBotsQuery())
  const { data: deleted } = useQuery(deletedBotsQuery())

  const count = data?.count ?? 0
  const lastPage = Math.max(1, Math.ceil(count / PAGE_SIZE))
  const words = lede(everything?.count ?? null, byBots?.count ?? null, order)
  const labels = pagerLabels(order)

  // Changing what is shown returns to the first page: the page a reader was
  // on may not exist under the new narrowing.
  const show = (next: Partial<typeof search>) =>
    navigate({
      search: (previous) => ({ ...previous, ...next, page: undefined }),
    })
  const goTo = (next: number) =>
    navigate({
      search: (previous) => ({
        ...previous,
        page: next === 1 ? undefined : next,
      }),
    })
  const turn = (next: LogOrder) =>
    show({ order: next === "newest" ? undefined : next })

  // A restore can empty the last page under a reader who changed nothing.
  useEffect(() => {
    if (data && page > lastPage) goTo(lastPage)
  })

  return (
    <div className="page-column">
      <h1 className="mb-1 text-[22px] leading-[1.2] font-semibold tracking-[-0.015em]">
        Activity
      </h1>
      <p className="text-ink-3 mb-5">
        <span className="text-ink font-medium">{words.lead}</span>
        {words.rest && ` ${words.rest}`}
      </p>

      {/* The narrowing is a control the reader can see and undo. A log that
          quietly answers a narrower question than the one being asked is
          worse than a log with no filter at all. */}
      <ActivityFilters search={search} onChange={show} onOrder={turn} />

      {isPending ? (
        <ActivityLogPending />
      ) : isError || !data ? (
        // A failed fetch is not an empty log: say so, and offer the retry.
        <div role="alert" className="border-rule border-b py-8">
          <p className="font-medium">The activity could not be loaded</p>
          <p className="text-ink-3 mt-1">
            Nothing is lost.{" "}
            <button
              type="button"
              onClick={() => void refetch()}
              className={cn(textLink, "text-ink underline")}
            >
              Try again
            </button>
          </p>
        </div>
      ) : data.data.length === 0 ? (
        <p className="text-ink-3 border-rule border-b py-8">
          {emptyMessage(search.actor, search.kind)}
        </p>
      ) : (
        <ActivityLog
          entries={data.data}
          currentUserId={currentUser?.id}
          deletedBotIds={new Set((deleted?.data ?? []).map((bot) => bot.id))}
        />
      )}

      {count > 0 && (
        <div className="text-ink-3 flex items-center gap-[18px] pt-3.5 text-[13px]">
          {/* The number the server counted under these narrowings, not the
              size of the window that was fetched. */}
          <p aria-live="polite">{pagerText(count, page, lastPage)}</p>
          <div
            className={cn("ml-auto flex gap-3.5", lastPage === 1 && "hidden")}
          >
            <PagerButton disabled={page <= 1} onClick={() => goTo(page - 1)}>
              <span aria-hidden>← </span>
              {labels.back}
            </PagerButton>
            <PagerButton
              disabled={page >= lastPage}
              onClick={() => goTo(page + 1)}
            >
              {labels.on}
              <span aria-hidden> →</span>
            </PagerButton>
          </div>
        </div>
      )}
    </div>
  )
}
