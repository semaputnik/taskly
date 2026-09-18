import { usePrefetchQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import {
  InProgress,
  InProgressPending,
  inProgressQuery,
} from "@/components/Dashboard/InProgress"
import { NeedsYou, NeedsYouPending } from "@/components/Dashboard/NeedsYou"
import {
  recentActivityQuery,
  WhileYouWereAway,
  WhileYouWereAwayPending,
} from "@/components/Dashboard/WhileYouWereAway"
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
  // Started here, beside the queue's own requests, rather than after the
  // queue has suspended and resumed: the sheets beside it are not rendered
  // until it resumes.
  usePrefetchQuery(recentActivityQuery())
  usePrefetchQuery(inProgressQuery())

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

      {/* The queue leads; beside it, what is already under way, then the log
          as context — not below the fold. On a phone the three stack in that
          order. */}
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        {/* One boundary: every sheet appears in the same frame, so none moves
            another once it is drawn. */}
        <Suspense
          fallback={
            <>
              <NeedsYouPending />
              <div className="flex flex-col gap-6">
                <InProgressPending />
                <WhileYouWereAwayPending />
              </div>
            </>
          }
        >
          <NeedsYou />
          <div className="flex flex-col gap-6">
            <InProgress />
            <WhileYouWereAway />
          </div>
        </Suspense>
      </div>
    </div>
  )
}
