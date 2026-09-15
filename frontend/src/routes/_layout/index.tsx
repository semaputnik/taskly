import { createFileRoute } from "@tanstack/react-router"
import { z } from "zod"

import { NeedsYou } from "@/components/Dashboard/NeedsYou"
import { WhileYouWereAway } from "@/components/Dashboard/WhileYouWereAway"
import { partOfDay } from "@/components/Dashboard/when"
import { openTaskSchema } from "@/components/Tasks/search"
import { TaskDetail } from "@/components/Tasks/TaskDetail"
import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  // The dashboard opens tasks in place, so it carries the panel's parameter
  // too: reading one task should not cost the reader this screen.
  validateSearch: z.object(openTaskSchema),
  head: () => ({
    meta: [
      {
        title: "Dashboard - Taskly",
      },
    ],
  }),
})

/** The first name alone, where there is one: a greeting is not a form field. */
function greetingName(fullName?: string | null, email?: string): string {
  const name = fullName?.trim()
  if (name) {
    return name.split(/\s+/)[0]
  }
  return email?.split("@")[0] ?? "there"
}

function Dashboard() {
  const { user: currentUser } = useAuth()
  const { task } = Route.useSearch()
  const navigate = Route.useNavigate()
  const openTask = (next: string | undefined) =>
    navigate({ search: { task: next } })

  return (
    <div className="flex flex-col gap-6">
      <TaskDetail
        taskId={task ?? null}
        onClose={() => openTask(undefined)}
        onOpenTask={openTask}
      />

      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Good {partOfDay()},{" "}
          {greetingName(currentUser?.full_name, currentUser?.email)}
        </h1>
        <p className="text-muted-foreground">
          What needs you now, and what changed without you
        </p>
      </div>

      {/* The queue leads; the log is context beside it, not below the fold. */}
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <NeedsYou />
        <WhileYouWereAway />
      </div>
    </div>
  )
}
