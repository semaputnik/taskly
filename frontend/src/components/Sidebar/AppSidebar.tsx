import { Link as RouterLink } from "@tanstack/react-router"
import { Plus } from "lucide-react"
import { useId } from "react"

import { Logo } from "@/components/Common/Logo"
import { useRecordPanels } from "@/components/Records/panels"
import useAuth from "@/hooks/useAuth"
import { cn } from "@/lib/utils"
import { type NavCount, useNavCounts } from "./counts"
import { navItemFocus } from "./styles"
import { User } from "./User"

interface NavItem {
  title: string
  path: string
}

const baseItems: NavItem[] = [
  { title: "Today", path: "/" },
  { title: "Tasks", path: "/tasks" },
  { title: "Projects", path: "/projects" },
  { title: "Tags", path: "/tags" },
  { title: "Bots", path: "/bots" },
  { title: "Activity", path: "/activity" },
  { title: "Archive", path: "/archive" },
]

const itemClass = cn(
  navItemFocus,
  "text-ink-2 hover:bg-hover hover:text-ink -mx-2 flex h-[30px] items-center justify-between gap-2 rounded-md px-2",
)

/**
 * The app's primary action: start capture, from the top of the navigation.
 *
 * It opens the task's own panel as a draft: the title and every property are
 * there at once, and one commit creates the task. The key cap says how to do
 * the same without the pointer.
 */
function CaptureEntry({ onNavigate }: { onNavigate?: () => void }) {
  const { capture } = useRecordPanels()
  return (
    <button
      type="button"
      aria-keyshortcuts="c"
      onClick={() => {
        onNavigate?.()
        capture("task")
      }}
      className={cn(itemClass, "text-ink w-[calc(100%+1rem)] text-left")}
    >
      <span className="flex items-center gap-2">
        <Plus aria-hidden className="text-ink-3 size-4" strokeWidth={1.6} />
        Add a task
      </span>
      <kbd
        aria-hidden
        className="text-ink-3 border-rule-strong rounded border px-[5px] font-mono text-[11px] leading-4"
      >
        C
      </kbd>
    </button>
  )
}

/**
 * One screen in the list. The count, where there is one, is read after the
 * name as a description, so the link is still named by the screen alone.
 */
function Item({
  item,
  count,
  onNavigate,
}: {
  item: NavItem
  count: NavCount | null | undefined
  onNavigate?: () => void
}) {
  const descriptionId = useId()
  return (
    <li>
      <RouterLink
        to={item.path}
        // The dashboard is the root, which every path starts with.
        activeOptions={{ exact: item.path === "/", includeSearch: false }}
        onClick={onNavigate}
        aria-describedby={count ? descriptionId : undefined}
        className={cn(
          itemClass,
          "data-[status=active]:text-ink data-[status=active]:font-semibold",
        )}
      >
        {item.title}
        {count && (
          <span
            aria-hidden
            className="text-ink-3 font-mono text-xs font-normal tabular-nums"
          >
            {count.figure}
          </span>
        )}
      </RouterLink>
      {count && (
        <span id={descriptionId} hidden>
          {count.description}
        </span>
      )}
    </li>
  )
}

/**
 * The navigation, as plain text: the wordmark, capture, the list of screens
 * with counts where a count means something, and the account at the foot.
 * Nothing marks the current screen but weight. The same list sits in the
 * left column on a wide screen and in the menu sheet on a phone;
 * `onNavigate` closes that sheet when a choice is made in it.
 */
export function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const { user: currentUser } = useAuth()
  const counts = useNavCounts()

  const items = currentUser?.is_superuser
    ? [...baseItems, { title: "Admin", path: "/admin" }]
    : baseItems

  return (
    <nav
      aria-label="Main"
      // The padding, taken back by the margin, keeps hover fills and focus
      // outlines that reach past the column inside the scrolling box.
      className="-m-2 flex h-[calc(100%+1rem)] min-h-0 flex-col gap-[26px] overflow-y-auto p-2"
    >
      <Logo className={cn(navItemFocus, "self-start rounded-sm")} />
      <ul className="flex flex-col gap-0.5">
        <li>
          <CaptureEntry onNavigate={onNavigate} />
        </li>
      </ul>
      <ul className="flex flex-col gap-0.5">
        {items.map((item) => (
          <Item
            key={item.path}
            item={item}
            count={counts[item.path]}
            onNavigate={onNavigate}
          />
        ))}
      </ul>
      <div className="mt-auto">
        <User user={currentUser} onNavigate={onNavigate} />
      </div>
    </nav>
  )
}
