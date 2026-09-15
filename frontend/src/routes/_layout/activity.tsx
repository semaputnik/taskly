import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Bot } from "lucide-react"
import { z } from "zod"

import { type ActivityEntryPublic, ActivityService } from "@/client"
import { ActivityDescription } from "@/components/Activity/ActivityDescription"
import { RestoreDeletion } from "@/components/Activity/RestoreDeletion"
import { Badge } from "@/components/ui/badge"
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

const PAGE_SIZE = 50

const activitySearchSchema = z.object({
  page: z.number().int().min(1).optional().catch(undefined),
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

/**
 * Who made the change: you, or one of your bot users by name (FR-10.2).
 */
function ActorLabel({
  entry,
  currentUserId,
}: {
  entry: ActivityEntryPublic
  currentUserId?: string
}) {
  if (entry.actor_bot_user_id) {
    return (
      <span className="inline-flex items-center gap-1.5">
        <Bot className="size-4 text-muted-foreground" aria-hidden />
        {entry.actor_bot_user_name ?? "A bot user"}
        <Badge variant="outline" className="text-xs">
          Bot
        </Badge>
      </span>
    )
  }
  return entry.actor_id === currentUserId ? "You" : "Someone else"
}

function ActivityRows({
  entries,
  currentUserId,
}: {
  entries: ActivityEntryPublic[]
  currentUserId?: string
}) {
  if (entries.length === 0) {
    return (
      <TableRow className="hover:bg-transparent">
        <TableCell
          colSpan={4}
          className="h-32 text-center text-muted-foreground"
        >
          Nothing has happened in your account yet.
        </TableCell>
      </TableRow>
    )
  }
  return entries.map((entry) => (
    <TableRow key={entry.id}>
      <TableCell className="whitespace-nowrap text-muted-foreground">
        {entry.created_at ? new Date(entry.created_at).toLocaleString() : ""}
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
  const { page = 1 } = Route.useSearch()
  const navigate = Route.useNavigate()
  const { user: currentUser } = useAuth()

  const query = { skip: (page - 1) * PAGE_SIZE, limit: PAGE_SIZE }
  const { data, isPending } = useQuery({
    queryKey: ["activity", query],
    queryFn: async () =>
      (await ActivityService.readActivityLog({ query })).data,
  })

  const count = data?.count ?? 0
  const lastPage = Math.max(1, Math.ceil(count / PAGE_SIZE))
  const goTo = (next: number) =>
    navigate({ search: { page: next === 1 ? undefined : next } })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Activity</h1>
        <p className="text-muted-foreground">
          Every change in your account, newest first
        </p>
      </div>

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
            <ActivityRows entries={data.data} currentUserId={currentUser?.id} />
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
