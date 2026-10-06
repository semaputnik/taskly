import { Link as RouterLink } from "@tanstack/react-router"
import { Bot, Calendar, Clock, ListTodo, LogOut, Plus } from "lucide-react"
import { type RefObject, useEffect, useMemo, useState } from "react"

import { CaptureLine } from "@/components/Dashboard/CaptureLine"
import { useRecordPanels } from "@/components/Records/panels"
import { titleHandedOff } from "@/components/Tasks/capture"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@/components/ui/sheet"
import useAuth from "@/hooks/useAuth"
import { useIsPhone } from "@/hooks/useIsPhone"
import { useVisualViewport } from "@/hooks/useVisualViewport"
import { cn } from "@/lib/utils"
import { navItemFocus } from "./styles"
import { AppearanceItems } from "./User"

const tabClass = cn(
  navItemFocus,
  "text-ink-3 data-[status=active]:text-ink flex h-full flex-col items-center justify-center gap-[3px] text-[11px] font-medium data-[status=active]:font-semibold focus-visible:-outline-offset-4",
)

/**
 * The phone's navigation: a bar of five at the foot of the screen, where a
 * thumb rests. Today and Tasks, the add control as a filled circle in the
 * middle, Bots and Activity. The screen the reader is on is marked by weight
 * and ink and never by colour, and is stated to a screen reader as the
 * current page. Projects, Tags, Archive and the rest are behind the account
 * control in the top bar (`AccountMenu`).
 *
 * The add control raises the capture sheet from any screen (FR-06.15). A
 * record's full-screen column covers the screen and takes the bar with it.
 */
export function TabBar({
  onAdd,
  addRef,
  adding,
}: {
  onAdd: () => void
  addRef: RefObject<HTMLButtonElement | null>
  adding: boolean
}) {
  return (
    <nav
      aria-label="Main"
      className="bg-page border-rule-strong fixed inset-x-0 bottom-0 z-30 border-t pb-[env(safe-area-inset-bottom)] md:hidden group-has-[[data-record-column]]/shell:hidden"
    >
      <ul className="grid h-14 grid-cols-5">
        <li>
          <RouterLink
            to="/"
            activeOptions={{ exact: true, includeSearch: false }}
            className={tabClass}
          >
            <Calendar aria-hidden className="size-[22px]" strokeWidth={1.6} />
            Today
          </RouterLink>
        </li>
        <li>
          <RouterLink to="/tasks" className={tabClass}>
            <ListTodo aria-hidden className="size-[22px]" strokeWidth={1.6} />
            Tasks
          </RouterLink>
        </li>
        <li>
          <button
            ref={addRef}
            type="button"
            aria-label="Add a task"
            aria-haspopup="dialog"
            aria-expanded={adding}
            onClick={onAdd}
            className={cn(
              navItemFocus,
              "grid h-full w-full place-items-center focus-visible:-outline-offset-4",
            )}
          >
            <span
              aria-hidden
              className="bg-ink text-page grid size-10 place-items-center rounded-full"
            >
              <Plus className="size-[22px]" strokeWidth={2} />
            </span>
          </button>
        </li>
        <li>
          <RouterLink to="/bots" className={tabClass}>
            <Bot aria-hidden className="size-[22px]" strokeWidth={1.6} />
            Bots
          </RouterLink>
        </li>
        <li>
          <RouterLink to="/activity" className={tabClass}>
            <Clock aria-hidden className="size-[22px]" strokeWidth={1.6} />
            Activity
          </RouterLink>
        </li>
      </ul>
    </nav>
  )
}

const menuItemClass = "min-h-11"

/**
 * The account control in the phone's top bar: the initial in a circle, which
 * opens what the bar has no room for — the screens that are not tabs,
 * appearance, and signing out. Settings is a place, so it is a link.
 */
export function AccountMenu() {
  const { user, logout } = useAuth()
  if (!user) return null

  const label = user.full_name || user.email
  const initial = (user.full_name || user.email).charAt(0).toUpperCase()
  const places = [
    { title: "Projects", to: "/projects" },
    { title: "Tags", to: "/tags" },
    { title: "Archive", to: "/archive" },
    { title: "Settings", to: "/settings" },
    ...(user.is_superuser ? [{ title: "Admin", to: "/admin" }] : []),
  ]

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Account"
        data-testid="account-menu"
        className={cn(
          navItemFocus,
          "hover:bg-hover data-[state=open]:bg-hover -mr-2 ml-auto grid size-11 place-items-center rounded-md",
        )}
      >
        <span
          aria-hidden
          className="bg-ink text-page grid size-[26px] place-items-center rounded-full text-xs font-semibold"
        >
          {initial}
        </span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-56">
        <DropdownMenuLabel className="font-normal">
          <p className="truncate text-sm font-medium">{label}</p>
          {user.full_name && (
            <p className="text-muted-foreground truncate text-xs">
              {user.email}
            </p>
          )}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {places.map((place) => (
          <DropdownMenuItem key={place.to} asChild className={menuItemClass}>
            <RouterLink to={place.to}>{place.title}</RouterLink>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <AppearanceItems itemClassName={menuItemClass} />
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={logout} className={menuItemClass}>
          <LogOut />
          Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/**
 * The capture sheet: the capture line, raised from the bar's add control over
 * a dimmed page, on any screen (FR-06.15).
 *
 * It carries the same line as the pages of a desktop, with its title search
 * (FR-06.14): Return creates, a tap on a match opens that task, and a "More
 * options…" line goes on to the full draft (ADR-0005), which is the only way a
 * phone has to give a task a day, a priority or another project before it
 * exists. The sheet sits above the keyboard, following the visual viewport
 * (`useVisualViewport`, which writes to the sheet's own element and nothing
 * else). Escape or a tap outside closes it and keeps what was typed; having
 * made a task, or opened one, it closes by itself, since its scrim would hold
 * the notice's actions out of reach.
 *
 * It is mounted once, beside the bar, so what is typed survives its closing.
 */
export function CaptureSheet({
  open,
  onOpenChange,
  returnFocusTo,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** The control that raised it, which gets focus back. */
  returnFocusTo: RefObject<HTMLElement | null>
}) {
  const panels = useRecordPanels()
  const phone = useIsPhone()
  const [title, setTitle] = useState("")
  const [content, setContent] = useState<HTMLElement | null>(null)
  const target = useMemo(() => ({ current: content }), [content])
  // Followed for as long as the sheet is in the page, its closing animation
  // included: dropped at `open: false`, it would fall to the bottom edge
  // while a keyboard is still going down.
  useVisualViewport(target, content !== null)

  // A phone turned to a wide screen has no add control, and so no sheet.
  useEffect(() => {
    if (!phone && open) onOpenChange(false)
  }, [phone, open, onOpenChange])

  // Words left over from an earlier hand-over are not this sheet's.
  useEffect(() => {
    if (open) titleHandedOff.clear()
  }, [open])

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        ref={setContent}
        side="bottom"
        showCloseButton={false}
        // Escape closes the matches before it closes the sheet: the line
        // answers it, and the sheet does not hear it.
        onEscapeKeyDown={(event) => {
          if (document.activeElement?.getAttribute("aria-expanded") === "true")
            event.preventDefault()
        }}
        // A tap does not focus a button on iOS, so the browser's own idea of
        // where focus was is unreliable; the control is named.
        onCloseAutoFocus={(event) => {
          event.preventDefault()
          returnFocusTo.current?.focus()
        }}
        className="bg-page bottom-[var(--kb-inset,0px)] max-h-[var(--vv-height,100svh)] gap-0 rounded-t-xl px-4 pt-2.5 pb-[max(0px,calc(env(safe-area-inset-bottom)-var(--kb-inset,0px)))] shadow-none data-[state=closed]:duration-150 data-[state=open]:duration-200"
      >
        <div
          aria-hidden
          className="bg-rule-strong mx-auto mb-2 h-1 w-9 shrink-0 rounded-full"
        />
        <SheetTitle className="sr-only">Add a task</SheetTitle>
        <SheetDescription className="sr-only">
          Write the task down and press Return, or choose one of the open tasks
          that match to open it.
        </SheetDescription>
        <CaptureLine
          sheet={{
            title,
            setTitle,
            onDone: () => onOpenChange(false),
            onMore: () => {
              titleHandedOff.set(title.trim())
              setTitle("")
              onOpenChange(false)
              panels.capture("task")
            },
          }}
        />
      </SheetContent>
    </Sheet>
  )
}
