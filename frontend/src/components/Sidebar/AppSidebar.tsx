import { Link as RouterLink, useRouterState } from "@tanstack/react-router"
import {
  Archive,
  Bot,
  CheckSquare,
  FolderKanban,
  History,
  Home,
  type LucideIcon,
  Settings,
  Tag,
  Users,
} from "lucide-react"

import { SidebarAppearance } from "@/components/Common/Appearance"
import AddTask from "@/components/Tasks/AddTask"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import useAuth from "@/hooks/useAuth"
import { cn } from "@/lib/utils"
import { Main, type NavItem } from "./Main"
import { User } from "./User"

const baseItems: NavItem[] = [
  { icon: Home, title: "Dashboard", path: "/" },
  { icon: CheckSquare, title: "Tasks", path: "/tasks" },
  { icon: FolderKanban, title: "Projects", path: "/projects" },
  { icon: Tag, title: "Tags", path: "/tags" },
  { icon: Archive, title: "Archive", path: "/archive" },
  // Activity and Settings are reached from the header actions above the list,
  // so they do not repeat here.
  { icon: Bot, title: "Bots", path: "/bots" },
]

/**
 * A square shortcut sitting beside a wider control. These are utilities reached
 * from anywhere, which is why they flank the account and appearance controls
 * rather than joining the navigation list.
 *
 * The 2rem box centres its icon on the same axis as every collapsed rail item,
 * so folding the sidebar changes what is visible without moving anything.
 */
function IconAction({
  icon: Icon,
  title,
  path,
}: {
  icon: LucideIcon
  title: string
  path: string
}) {
  const { isMobile, setOpenMobile } = useSidebar()
  const currentPath = useRouterState().location.pathname
  const isActive = currentPath === path

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <RouterLink
          to={path}
          aria-label={title}
          onClick={() => {
            if (isMobile) setOpenMobile(false)
          }}
          className={cn(
            "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-sidebar-ring grid size-8 shrink-0 place-content-center rounded-md outline-none transition-colors focus-visible:ring-2",
            isActive
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-muted-foreground",
          )}
        >
          <Icon className="size-4" />
        </RouterLink>
      </TooltipTrigger>
      <TooltipContent side="right" align="center">
        {title}
      </TooltipContent>
    </Tooltip>
  )
}

export function AppSidebar() {
  const { user: currentUser } = useAuth()
  const { open } = useSidebar()

  const items = currentUser?.is_superuser
    ? [...baseItems, { icon: Users, title: "Admin", path: "/admin" }]
    : baseItems

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="gap-3 px-2 py-3">
        <div className="flex items-center gap-1 group-data-[collapsible=icon]:flex-col group-data-[collapsible=icon]:gap-1">
          <User user={currentUser} />
          <IconAction icon={History} title="Activity" path="/activity" />
          <Tooltip>
            <TooltipTrigger asChild>
              <SidebarTrigger className="text-muted-foreground size-8 shrink-0" />
            </TooltipTrigger>
            <TooltipContent side="right" align="center">
              {open ? "Collapse sidebar" : "Expand sidebar"}
            </TooltipContent>
          </Tooltip>
        </div>
        <AddTask trigger="sidebar" />
      </SidebarHeader>
      <SidebarContent>
        <Main items={items} />
      </SidebarContent>
      <SidebarFooter>
        <div className="flex items-center gap-1 group-data-[collapsible=icon]:flex-col group-data-[collapsible=icon]:gap-1">
          <SidebarMenu className="min-w-0 flex-1">
            <SidebarAppearance />
          </SidebarMenu>
          <IconAction icon={Settings} title="Settings" path="/settings" />
        </div>
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
