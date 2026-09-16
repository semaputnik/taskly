import { Link as RouterLink } from "@tanstack/react-router"
import { ChevronDown, LogOut, Settings } from "lucide-react"

import type { UserPublic } from "@/client"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useSidebar } from "@/components/ui/sidebar"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import useAuth from "@/hooks/useAuth"
import { getInitials } from "@/utils"

interface UserInfoProps {
  fullName?: string
  email?: string
}

function UserInfo({ fullName, email }: UserInfoProps) {
  return (
    <div className="flex w-full min-w-0 items-center gap-2.5">
      <Avatar className="size-8">
        <AvatarFallback className="bg-secondary text-secondary-foreground">
          {getInitials(fullName || "User")}
        </AvatarFallback>
      </Avatar>
      <div className="flex min-w-0 flex-col items-start">
        <p className="w-full truncate text-sm font-medium">{fullName}</p>
        <p className="text-muted-foreground w-full truncate text-xs">{email}</p>
      </div>
    </div>
  )
}

/**
 * The account control at the top of the sidebar: who you are acting as, and
 * the way out. Collapsed to the icon rail it keeps only the avatar, so the
 * rail still answers "whose account is this".
 */
export function User({ user }: { user: UserPublic | null | undefined }) {
  const { logout } = useAuth()
  const { isMobile, setOpenMobile, state } = useSidebar()

  if (!user) return null

  const name = user.full_name || user.email
  const handleMenuClick = () => {
    if (isMobile) {
      setOpenMobile(false)
    }
  }

  return (
    <DropdownMenu>
      <Tooltip>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger
            data-testid="user-menu"
            className="hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-sidebar-ring data-[state=open]:bg-sidebar-accent flex min-w-0 flex-1 items-center gap-2 rounded-md p-1 text-left outline-none transition-colors focus-visible:ring-2 group-data-[collapsible=icon]:size-8 group-data-[collapsible=icon]:flex-none group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:p-0"
          >
            {/* 1.5rem inside the trigger's 0.25rem padding puts the avatar on
                the same centre line as every icon below it, so collapsing the
                sidebar does not shift the column. */}
            <Avatar className="size-6 shrink-0">
              <AvatarFallback className="bg-secondary text-secondary-foreground text-xs">
                {getInitials(name)}
              </AvatarFallback>
            </Avatar>
            <span className="truncate text-sm font-medium group-data-[collapsible=icon]:hidden">
              {name}
            </span>
            <ChevronDown className="text-muted-foreground size-4 shrink-0 group-data-[collapsible=icon]:hidden" />
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <TooltipContent
          side="right"
          align="center"
          hidden={state !== "collapsed" || isMobile}
        >
          {name}
        </TooltipContent>
      </Tooltip>

      <DropdownMenuContent className="min-w-56" side="bottom" align="start">
        <DropdownMenuLabel className="font-normal">
          <UserInfo fullName={user.full_name ?? undefined} email={user.email} />
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <RouterLink to="/settings" onClick={handleMenuClick}>
          <DropdownMenuItem>
            <Settings />
            User Settings
          </DropdownMenuItem>
        </RouterLink>
        <DropdownMenuItem onClick={logout}>
          <LogOut />
          Log Out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
