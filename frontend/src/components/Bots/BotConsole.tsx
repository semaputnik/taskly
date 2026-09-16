import { useQuery } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"

import {
  ActivityService,
  type BotUserPublic,
  type TaskPublic,
  TasksService,
} from "@/client"
import { ActivityDescription } from "@/components/Activity/ActivityDescription"
import { useRecordPanels } from "@/components/Records/panels"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useAuth from "@/hooks/useAuth"
import { ago } from "./health"

/**
 * What a bot user is doing, read where the bot user is read.
 *
 * The product's distinctive fact is that a person and their agents work the
 * same records, and the log has always known which agent did what — but the
 * only way to ask was to scroll the whole account's history. Here the two
 * questions an operator actually has are answered side by side: what has it
 * done, and what is it on.
 *
 * Both are previews. Past a handful of rows each hands off to the surface
 * built for the long version, filtered to this bot user.
 */

const PREVIEW = 5

export function BotConsole({ bot }: { bot: BotUserPublic }) {
  return (
    <Tabs
      defaultValue="activity"
      className="gap-4 border-t px-6 py-5"
      // Remounting per bot user keeps one agent's feed from appearing under
      // the next one.
      key={bot.id}
    >
      <TabsList>
        <TabsTrigger value="activity">Activity</TabsTrigger>
        <TabsTrigger value="tasks">Tasks</TabsTrigger>
      </TabsList>

      {/* Each collection's request waits until that collection is on screen. */}
      <TabsContent value="activity">
        <BotActivity bot={bot} />
      </TabsContent>
      <TabsContent value="tasks">
        <BotTasks bot={bot} />
      </TabsContent>
    </Tabs>
  )
}

function BotActivity({ bot }: { bot: BotUserPublic }) {
  const { user: currentUser } = useAuth()
  const query = { actor_bot_user_id: bot.id, skip: 0, limit: PREVIEW }
  const { data, isPending } = useQuery({
    queryKey: ["activity", query],
    queryFn: async () =>
      (await ActivityService.readActivityLog({ query })).data,
  })

  if (isPending || !data) return <PreviewSkeleton />

  if (data.count === 0) {
    return (
      <Empty>
        Nothing yet. Every change this bot user makes — a task created, a
        comment added, a tag applied — is recorded here, newest first.
      </Empty>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <ul
        aria-label={`Recent activity by ${bot.name}`}
        className="flex flex-col"
      >
        {data.data.map((entry) => (
          <li
            key={entry.id}
            className="flex flex-col gap-0.5 border-b py-2 last:border-b-0"
          >
            <span className="text-sm">
              <ActivityDescription
                entry={entry}
                currentUserId={currentUser?.id}
              />
            </span>
            <span className="text-muted-foreground text-xs">
              {ago(entry.created_at)}
            </span>
          </li>
        ))}
      </ul>
      <HandOff
        to="/activity"
        search={{ actor: bot.id }}
        count={data.count}
        shown={data.data.length}
        one="entry"
        many="entries"
        where="the activity log"
      />
    </div>
  )
}

function BotTasks({ bot }: { bot: BotUserPublic }) {
  const { openTask } = useRecordPanels()
  const query = { assignee_id: bot.id, skip: 0, limit: PREVIEW }
  const { data, isPending } = useQuery({
    queryKey: ["tasks", query],
    queryFn: async () => (await TasksService.readTasks({ query })).data,
  })

  if (isPending || !data) return <PreviewSkeleton />

  if (data.count === 0) {
    return (
      <Empty>
        No tasks are assigned to this bot user. Assign one from a task's panel
        to make this agent responsible for it.
      </Empty>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <ul
        aria-label={`Tasks assigned to ${bot.name}`}
        className="flex flex-col gap-2"
      >
        {data.data.map((task: TaskPublic) => (
          <li key={task.id}>
            <button
              type="button"
              // Opening a task from here swaps the panel to the task, and Back
              // brings this bot user's panel with its own address back.
              onClick={() => openTask(task.id)}
              className="hover:bg-accent flex w-full items-center gap-3 rounded-md border px-3 py-2 text-left text-sm transition-colors"
            >
              <span
                className={`min-w-0 flex-1 truncate ${
                  task.completed ? "text-muted-foreground line-through" : ""
                }`}
              >
                {task.title}
              </span>
              {task.due_date && (
                <span className="text-muted-foreground shrink-0 text-xs">
                  {task.due_date}
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>
      <HandOff
        to="/tasks"
        search={{ assignee: bot.id }}
        count={data.count}
        shown={data.data.length}
        one="task"
        many="tasks"
        where="the task list"
      />
    </div>
  )
}

/**
 * Where a preview ends and the real surface begins. A long list belongs in
 * the screen built for it, filtered to this bot user.
 */
function HandOff({
  to,
  search,
  count,
  shown,
  one,
  many,
  where,
}: {
  to: "/activity" | "/tasks"
  search: Record<string, string>
  count: number
  shown: number
  /** English does not pluralise by rule, so both words are given. */
  one: string
  many: string
  where: string
}) {
  const more = count - shown
  return (
    <RouterLink
      to={to}
      search={search}
      className="text-muted-foreground hover:text-foreground text-sm underline-offset-4 hover:underline"
    >
      {more > 0
        ? `${more} more ${more === 1 ? one : many} in ${where}`
        : `Open ${where}`}
    </RouterLink>
  )
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-muted-foreground text-sm text-pretty italic">
      {children}
    </p>
  )
}

function PreviewSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: 3 }).map((_, index) => (
        <Skeleton key={index} className="h-8 w-full" />
      ))}
    </div>
  )
}
