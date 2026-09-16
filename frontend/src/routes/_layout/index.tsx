import { createFileRoute } from "@tanstack/react-router"

import { NeedsYou } from "@/components/Dashboard/NeedsYou"
import { WhileYouWereAway } from "@/components/Dashboard/WhileYouWereAway"
import { partOfDay } from "@/components/Dashboard/when"
import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
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

  return (
    <div className="flex flex-col gap-6">
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
