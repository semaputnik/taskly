import { createFileRoute, Outlet, redirect } from "@tanstack/react-router"
import { Menu } from "lucide-react"
import { useState } from "react"

import { Logo } from "@/components/Common/Logo"
import { panelSearchSchema } from "@/components/Records/panels"
import { RecordPanels } from "@/components/Records/RecordPanels"
import { Navigation } from "@/components/Sidebar/AppSidebar"
import { navItemFocus } from "@/components/Sidebar/styles"
import { AddTaskButton } from "@/components/Tasks/AddTaskButton"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
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
})

/**
 * Below the tablet width the navigation folds into a top bar: the wordmark,
 * and a menu button that opens the same list in a sheet from the left.
 */
function TopBar() {
  const [open, setOpen] = useState(false)
  const close = () => setOpen(false)
  return (
    <header className="bg-page border-rule sticky top-0 z-10 flex h-14 items-center gap-3 border-b px-4 md:hidden">
      <Logo className={cn(navItemFocus, "rounded-sm")} />
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger
          aria-label="Menu"
          className={cn(
            navItemFocus,
            "hover:bg-hover -mr-2 ml-auto grid size-11 place-items-center rounded-md",
          )}
        >
          <Menu aria-hidden className="size-[18px]" strokeWidth={1.6} />
        </SheetTrigger>
        <SheetContent
          side="left"
          className="bg-page w-[264px] gap-0 px-7 py-7 shadow-none"
        >
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <SheetDescription className="sr-only">
            The screens of Taskly and your account.
          </SheetDescription>
          <Navigation onNavigate={close} />
        </SheetContent>
      </Sheet>
    </header>
  )
}

function Layout() {
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
      <div className="bg-page min-h-svh md:grid md:grid-cols-[200px_minmax(0,1fr)]">
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
            clear of the Add a task button, so the last row can always be
            scrolled out from under it. */}
        <main
          id="main"
          tabIndex={-1}
          className="min-w-0 px-4 pt-5 pb-28 outline-none md:px-12 md:pt-9 md:pb-24"
        >
          <div className="max-w-7xl">
            <Outlet />
          </div>
        </main>
      </div>
      {/* Mounted once: a record opens over whatever screen the reader is on,
          and capture starts from any of them. */}
      <RecordPanels />
      <AddTaskButton />
    </>
  )
}
