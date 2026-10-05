import { usePrefetchQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense, useEffect, useState } from "react"

import { CaptureLine } from "@/components/Dashboard/CaptureLine"
import {
  Changes,
  ChangesPending,
  changesQuery,
} from "@/components/Dashboard/Changes"
import { Day, DayHeading, DayPending } from "@/components/Dashboard/DayPage"
import { markSeen, visitSince } from "@/components/Dashboard/day"
import {
  InProgress,
  InProgressPending,
  inProgressQuery,
} from "@/components/Dashboard/InProgress"

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

/** When this visit counts the bot users' changes from, fixed for the session. */
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

  // The page is read until the reader leaves it — another screen, another
  // tab, or the browser closing — so that is when the look is remembered.
  useEffect(() => {
    const seen = () => {
      try {
        markSeen({ local: localStorage, session: sessionStorage }, new Date())
      } catch {
        // As above: blocked storage only costs the next visit its count.
      }
    }
    const onVisibility = () => {
      if (document.visibilityState === "hidden") seen()
    }
    document.addEventListener("visibilitychange", onVisibility)
    window.addEventListener("pagehide", seen)
    return () => {
      document.removeEventListener("visibilitychange", onVisibility)
      window.removeEventListener("pagehide", seen)
      seen()
    }
  }, [])
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
  usePrefetchQuery(changesQuery(since))
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
              <ChangesPending />
            </div>
          </>
        }
      >
        <Day since={since} />
        <div className="flex flex-col gap-6">
          <InProgress />
          <Changes since={since} />
        </div>
      </Suspense>
    </div>
  )
}
