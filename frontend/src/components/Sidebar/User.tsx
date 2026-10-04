import { Link as RouterLink } from "@tanstack/react-router"
import { ChevronDown, LogOut, Settings } from "lucide-react"

import type { UserPublic } from "@/client"
import { type Theme, useTheme } from "@/components/theme-provider"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useAuth from "@/hooks/useAuth"
import { navItemFocus } from "./styles"

const THEMES: { value: Theme; label: string; testId?: string }[] = [
  { value: "light", label: "Light", testId: "light-mode" },
  { value: "dark", label: "Dark", testId: "dark-mode" },
  { value: "system", label: "System" },
]

/**
 * The account row at the foot of the navigation: an initial avatar and the
 * name, which open the account menu (appearance, log out), beside a settings
 * glyph. Settings is a place, so it is a link and not a menu entry.
 */
export function User({
  user,
  onNavigate,
}: {
  user: UserPublic | null | undefined
  onNavigate?: () => void
}) {
  const { logout } = useAuth()
  const { theme, setTheme } = useTheme()

  if (!user) return null

  const name = user.full_name || user.email

  return (
    <div className="-ml-2 flex items-center gap-1">
      <DropdownMenu>
        <DropdownMenuTrigger
          data-testid="user-menu"
          className={`${navItemFocus} text-ink-2 hover:bg-hover hover:text-ink data-[state=open]:bg-hover data-[state=open]:text-ink flex h-[34px] min-w-0 flex-1 items-center gap-2 rounded-md px-2 text-left text-[13px]`}
        >
          <span
            aria-hidden
            className="bg-ink text-page grid size-5 flex-none place-items-center rounded-full text-[11px] font-semibold"
          >
            {name.charAt(0).toUpperCase()}
          </span>
          <span className="min-w-0 truncate" title={name}>
            {name}
          </span>
          <ChevronDown aria-hidden className="text-ink-3 size-3 flex-none" />
        </DropdownMenuTrigger>
        <DropdownMenuContent className="min-w-56" side="top" align="start">
          <DropdownMenuLabel className="font-normal">
            <p className="truncate text-sm font-medium">{name}</p>
            {user.full_name && (
              <p className="text-muted-foreground truncate text-xs">
                {user.email}
              </p>
            )}
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuLabel className="text-muted-foreground text-xs font-normal">
            Appearance
          </DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={theme}
            onValueChange={(value) => setTheme(value as Theme)}
          >
            {THEMES.map(({ value, label, testId }) => (
              <DropdownMenuRadioItem
                key={value}
                value={value}
                data-testid={testId}
              >
                {label}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={logout}>
            <LogOut />
            Log out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <RouterLink
        to="/settings"
        aria-label="Settings"
        onClick={onNavigate}
        className={`${navItemFocus} text-ink-3 hover:bg-hover hover:text-ink data-[status=active]:text-ink grid size-[30px] flex-none place-items-center rounded-md`}
      >
        <Settings aria-hidden className="size-4" strokeWidth={1.6} />
      </RouterLink>
    </div>
  )
}
