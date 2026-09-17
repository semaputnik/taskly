import { createFileRoute, Outlet, redirect } from "@tanstack/react-router"
import { panelSearchSchema } from "@/components/Records/panels"
import { RecordPanels } from "@/components/Records/RecordPanels"
import AppSidebar from "@/components/Sidebar/AppSidebar"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { isLoggedIn } from "@/hooks/useAuth"

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

function Layout() {
  return (
    <SidebarProvider>
      <AppSidebar />
      {/* `min-w-0`: a flex item never shrinks below its content by default, so
          one long table row would widen the whole page instead of scrolling
          inside its own container. */}
      <SidebarInset className="min-w-0">
        {/* On a wide screen the sidebar carries its own collapse control, so
            the work area starts at the top. Below `md` the sidebar is an
            off-canvas sheet and this is the only way to summon it. */}
        <header className="bg-background sticky top-0 z-10 flex h-14 shrink-0 items-center border-b px-4 md:hidden">
          <SidebarTrigger className="text-muted-foreground -ml-1" />
        </header>
        {/* SidebarInset is already the page's one `main` landmark. */}
        <div className="flex-1 p-6 md:p-8">
          <div className="mx-auto max-w-7xl">
            <Outlet />
          </div>
        </div>
      </SidebarInset>
      {/* Mounted once: a record opens over whatever screen the reader is on,
          and capture starts from any of them. */}
      <RecordPanels />
    </SidebarProvider>
  )
}
