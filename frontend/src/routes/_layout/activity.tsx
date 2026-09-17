import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { z } from "zod"

import type { ActivityEntryPublic } from "@/client"
import { ActivityDescription } from "@/components/Activity/ActivityDescription"
import { ActorLabel } from "@/components/Activity/ActorLabel"
import { RestoreDeletion } from "@/components/Activity/RestoreDeletion"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import useAuth from "@/hooks/useAuth"
import { formatDateTime } from "@/lib/dates"
import { activityQuery, botQuery } from "@/lib/serverState"

const PAGE_SIZE = 50

const activitySearchSchema = z.object({
  page: z.number().int().min(1).optional().catch(undefined),
  // The log narrowed to one bot user: what its panel hands off to when its
  // feed runs past the preview.
  actor: z.string().uuid().optional().catch(undefined),
})

export const Route = createFileRoute("/_layout/activity")({
  component: Activity,
  validateSearch: activitySearchSchema,
  head: () => ({
    meta: [
      {
        title: "Activity - Taskly",
      },
    ],
  }),
})

function ActivityRows({
  entries,
  currentUserId,
  empty,
}: {
  entries: ActivityEntryPublic[]
  currentUserId?: string
  empty: string
}) {
  if (entries.length === 0) {
    return (
      <TableRow className="hover:bg-transparent">
        <TableCell
          colSpan={4}
          className="h-32 text-center text-muted-foreground"
        >
          {empty}
        </TableCell>
      </TableRow>
    )
  }
  return entries.map((entry) => (
    <TableRow key={entry.id}>
      <TableCell className="whitespace-nowrap text-muted-foreground">
        {entry.created_at ? formatDateTime(entry.created_at) : ""}
      </TableCell>
      <TableCell className="whitespace-nowrap">
        <ActorLabel entry={entry} currentUserId={currentUserId} />
      </TableCell>
      <TableCell>
        <ActivityDescription entry={entry} currentUserId={currentUserId} />
      </TableCell>
      <TableCell className="text-right">
        {entry.restorable && <RestoreDeletion entry={entry} />}
      </TableCell>
    </TableRow>
  ))
}

function PendingRows() {
  return Array.from({ length: 5 }).map((_, index) => (
    <TableRow key={index}>
      <TableCell>
        <Skeleton className="h-4 w-32" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-4 w-12" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-4 w-64" />
      </TableCell>
      <TableCell />
    </TableRow>
  ))
}

/**
 * The user's activity log, newest first (FR-10.1). Only ever their own
 * entries: the API offers no way to ask for anyone else's (FR-10.7).
 */
function Activity() {
  const { page = 1, actor } = Route.useSearch()
  const navigate = Route.useNavigate()
  const { user: currentUser } = useAuth()

  const query = {
    skip: (page - 1) * PAGE_SIZE,
    limit: PAGE_SIZE,
    actor_bot_user_id: actor,
  }
  const { data, isPending } = useQuery(activityQuery(query))
  // Named from the bot user itself rather than from the feed: a filter that
  // matches nothing still has to say whose nothing it is. A deleted bot user
  // reads here too (FR-08.19).
  const { data: actorBot } = useQuery(botQuery(actor))

  const count = data?.count ?? 0
  const lastPage = Math.max(1, Math.ceil(count / PAGE_SIZE))
  const goTo = (next: number) =>
    navigate({
      search: (previous) => ({
        ...previous,
        page: next === 1 ? undefined : next,
      }),
    })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Activity</h1>
        <p className="text-muted-foreground">
          Every change in your account, newest first
        </p>
      </div>

      {actor && (
        // A narrowed log says so where it is read, and offers the way back:
        // a filter that is not visible is a log that looks wrong.
        <div className="bg-card flex flex-wrap items-center gap-3 rounded-lg border px-4 py-3">
          <span className="text-sm">
            Showing only what{" "}
            <span className="font-medium">
              {actorBot?.name ?? "this bot user"}
            </span>{" "}
            did
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              navigate({
                search: (previous) => ({
                  ...previous,
                  actor: undefined,
                  page: undefined,
                }),
              })
            }
          >
            Show everything
          </Button>
        </div>
      )}

      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead>When</TableHead>
            <TableHead>Who</TableHead>
            <TableHead>What</TableHead>
            <TableHead>
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isPending || !data ? (
            <PendingRows />
          ) : (
            <ActivityRows
              entries={data.data}
              currentUserId={currentUser?.id}
              empty={
                actor
                  ? "This bot user has not changed anything yet."
                  : "Nothing has happened in your account yet."
              }
            />
          )}
        </TableBody>
      </Table>

      {count > PAGE_SIZE && (
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm text-muted-foreground">
            Page {page} of {lastPage}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => goTo(page - 1)}
            >
              Newer
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= lastPage}
              onClick={() => goTo(page + 1)}
            >
              Older
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
