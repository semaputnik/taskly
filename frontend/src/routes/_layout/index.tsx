import { usePrefetchQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense, useState } from "react"

import { CaptureLine } from "@/components/Dashboard/CaptureLine"
import { Day, DayHeading, DayPending } from "@/components/Dashboard/DayPage"
import { visitSince } from "@/components/Dashboard/day"
import {
  InProgress,
  InProgressPending,
  inProgressQuery,
} from "@/components/Dashboard/InProgress"
import {
  recentActivityQuery,
  WhileYouWereAway,
  WhileYouWereAwayPending,
} from "@/components/Dashboard/WhileYouWereAway"

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

/** When this visit counts the agents' changes from, fixed for the session. */
function useVisitSince(): string | null {
  const [since] = useState(() => {
    // Merely reaching for storage throws where site data is blocked.
    try {
      return visitSince(
        { local: localStorage, session: sessionStorage },
        new Date(),
      )
    } catch {
      return null
    }
  })
  return since
}

/**
 * The day page: today read as one column. The capture line first, then the
 * date and one sentence of what needs the reader, then the date bands, and
 * beneath them what is under way and what changed.
 */
function Dashboard() {
  const since = useVisitSince()
  // Started here, beside the bands' own requests, rather than after the
  // bands have suspended and resumed: the sections below them are not
  // rendered until they resume.
  usePrefetchQuery(recentActivityQuery())
  usePrefetchQuery(inProgressQuery())

  return (
    <div className="max-w-[820px]">
      <div className="mb-6 md:mb-9">
        <CaptureLine />
      </div>
      {/* Needs nothing from the server, so it is never a skeleton. */}
      <DayHeading />

      {/* One boundary: every section appears in the same frame, so none
          moves another once it is drawn. The two panels below keep their
          old form until their own slices replace them. */}
      <Suspense
        fallback={
          <>
            <DayPending />
            <div className="flex flex-col gap-6">
              <InProgressPending />
              <WhileYouWereAwayPending />
            </div>
          </>
        }
      >
        <Day since={since} />
        <div className="flex flex-col gap-6">
          <InProgress />
          <WhileYouWereAway />
        </div>
      </Suspense>
    </div>
  )
}
