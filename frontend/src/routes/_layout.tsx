import { createFileRoute, Outlet, redirect } from "@tanstack/react-router"
import { useRef, useState } from "react"

import { Wordmark } from "@/components/Common/Wordmark"
import { preloadPanel } from "@/components/Records/panelModules"
import { openPanelKind, panelSearchSchema } from "@/components/Records/panels"
import { RecordPanels } from "@/components/Records/RecordPanels"
import { Navigation } from "@/components/Sidebar/AppSidebar"
import {
  AccountMenu,
  CaptureSheet,
  TabBar,
} from "@/components/Sidebar/PhoneNav"
import { navItemFocus } from "@/components/Sidebar/styles"
import { isLoggedIn } from "@/hooks/useAuth"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/_layout")({
  component: Layout,
  // The panel and capture are validated here, so every authenticated screen
  // carries them (The Stay-Put Rule).
  validateSearch: panelSearchSchema,
  beforeLoad: async () => {
    if (!isLoggedIn()) {
      throw redirect({
        to: "/login",
      })
    }
  },
  // An address that already has a record open fetches that panel's code
  // beside the page's, rather than once the page has drawn.
  loader: ({ location }) => {
    const search = panelSearchSchema.safeParse(location.search)
    const kind = search.success ? openPanelKind(search.data) : undefined
    if (kind) preloadPanel(kind)
  },
})

/**
 * Below the tablet width the navigation moves to the bottom of the screen
 * (`TabBar`), and the top bar keeps the wordmark and gains the labelled
 * Menu control, which holds what the bar has no room for.
 */
function TopBar() {
  return (
    <header className="bg-page border-rule sticky top-0 z-10 flex h-11 items-center gap-3 border-b px-4 md:hidden">
      <Wordmark className={cn(navItemFocus, "rounded-sm")} />
      <AccountMenu />
    </header>
  )
}

function Layout() {
  // The add control raises the capture sheet from any screen; the bar and the
  // sheet share it, and the sheet hands focus back to the control.
  const [adding, setAdding] = useState(false)
  const [held, setHeld] = useState(false)
  const addControl = useRef<HTMLButtonElement>(null)
  return (
    <>
      <a
        href="#main"
        className={cn(
          navItemFocus,
          "bg-page text-ink border-rule-strong sr-only z-50 rounded-md border px-3 py-2 text-sm font-medium focus-visible:not-sr-only focus-visible:fixed focus-visible:top-3 focus-visible:left-3",
        )}
      >
        Skip to content
      </a>
      {/* A record opens in a third column beside the page, which is why the
          grid has a track for it: empty, it is no width at all, and it grows
          to the column's 560px as one opens, so the page gives way in one
          motion rather than jumping. Below 1200px the column is fixed over
          the screen and takes no track. The grid clips, not scrolls, while
          the track is growing. */}
      <div className="group/shell bg-page min-h-svh md:grid md:grid-cols-[200px_minmax(0,1fr)_0px] min-[1200px]:overflow-x-clip min-[1200px]:transition-[grid-template-columns] min-[1200px]:duration-[260ms] min-[1200px]:ease-[cubic-bezier(0.16,1,0.3,1)] min-[1200px]:has-[[data-record-column]]:grid-cols-[200px_minmax(0,1fr)_560px] motion-reduce:transition-none">
        {/* On a wide screen the navigation is a column of its own, held in
            place while the page scrolls. No rule divides it from the work:
            whitespace does. */}
        <div className="sticky top-0 hidden h-svh py-7 pr-5 pl-7 md:block">
          <Navigation />
        </div>
        <TopBar />
        {/* `min-w-0`: a grid item never shrinks below its content by default,
            so one long table row would widen the whole page instead of
            scrolling inside its own container. On a phone the foot is kept
            clear of the tab bar at the bottom of the screen, so the last row
            can always be scrolled out from under it. */}
        <main
          id="main"
          tabIndex={-1}
          className="@container min-w-0 px-4 pt-5 pb-[calc(5rem+env(safe-area-inset-bottom))] outline-none md:px-12 md:pt-9 md:pb-24 min-[1200px]:transition-[padding] min-[1200px]:duration-[260ms] min-[1200px]:ease-[cubic-bezier(0.16,1,0.3,1)] min-[1200px]:group-has-[[data-record-column]]/shell:px-8 motion-reduce:transition-none"
        >
          <div className="max-w-7xl">
            <Outlet />
          </div>
        </main>
        {/* Mounted once: a record opens beside whatever screen the reader is
            on, and capture starts from any of them. */}
        <RecordPanels />
        <TabBar
          onAdd={() => setAdding(true)}
          addRef={addControl}
          adding={adding}
          held={held}
        />
        <CaptureSheet
          open={adding}
          onOpenChange={setAdding}
          returnFocusTo={addControl}
          onHeldChange={setHeld}
        />
      </div>
    </>
  )
}
