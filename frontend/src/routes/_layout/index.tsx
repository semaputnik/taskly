import { createFileRoute } from "@tanstack/react-router"
import { Suspense, useEffect, useState } from "react"

import { PageCaptureLine } from "@/components/Dashboard/CaptureLine"
import { Changes, ChangesPending } from "@/components/Dashboard/Changes"
import { Day, DayHeading, DayPending } from "@/components/Dashboard/DayPage"
import {
  markSeen,
  peekVisitSince,
  visitSince,
} from "@/components/Dashboard/day"
import {
  MyWork,
  MyWorkPending,
  usePrefetchMyWork,
} from "@/components/Dashboard/MyWork"
import { prefetchDay } from "@/components/Dashboard/queries"
import { Section } from "@/components/Dashboard/Section"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  // The requests start as soon as the route is matched, beside the download
  // of the page's own code rather than after it: on a slow connection that
  // is a round of requests the page no longer waits for. Nothing waits on
  // them here, and what is cached is left alone.
  loader: ({ context }) => {
    let since: string | null = null
    try {
      since = peekVisitSince({ local: localStorage, session: sessionStorage })
    } catch {
      // Merely reaching for storage throws where site data is blocked.
    }
    prefetchDay(context.queryClient, since)
  },
  head: () => ({
    meta: [
      {
        title: "Today - Taskly",
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
 * beneath them what is in the reader's hands and what changed.
 */
function Dashboard() {
  const since = useVisitSince()
  // Every section's request was started by the route's loader. The page
  // also watches My work, the last of them to answer, since it waits on
  // knowing the reader: its answer re-renders the page, and the sections
  // come in with that render. Left to resume on their own, React holds a
  // boundary's content back until 300ms after its skeleton was drawn.
  usePrefetchMyWork()

  return (
    <div className="max-w-[820px]">
      <PageCaptureLine className="mb-9" />
      {/* Needs nothing from the server, so it is never a skeleton. */}
      <DayHeading />

      {/* One boundary: every section appears in the same frame, so none
          moves another once it is drawn. */}
      <Suspense
        fallback={
          <>
            <DayPending />
            <MyWorkPending />
            <ChangesPending />
          </>
        }
      >
        <Section name="What is due">
          <Day since={since} />
        </Section>
        <Section name="In my hands">
          <MyWork />
        </Section>
        <Section name="Changes">
          <Changes since={since} />
        </Section>
      </Suspense>
    </div>
  )
}
