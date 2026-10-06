import { Link as RouterLink } from "@tanstack/react-router"
import { useId } from "react"

import { Wordmark } from "@/components/Common/Wordmark"
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
 * One screen in the list. The count, where there is one, is read after the
 * name as a description, so the link is still named by the screen alone.
 */
function Item({
  item,
  count,
}: {
  item: NavItem
  count: NavCount | null | undefined
}) {
  const descriptionId = useId()
  return (
    <li>
      <RouterLink
        to={item.path}
        // The dashboard is the root, which every path starts with.
        activeOptions={{ exact: item.path === "/", includeSearch: false }}
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
 * The navigation, as plain text: the wordmark, the list of screens
 * with counts where a count means something, and the account at the foot.
 * Nothing marks the current screen but weight. It is the left column of a
 * wide screen; a phone's navigation is the bar at the bottom (`PhoneNav`).
 */
export function Navigation() {
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
      <Wordmark className={cn(navItemFocus, "self-start rounded-sm")} />
      <ul className="flex flex-col gap-0.5">
        {items.map((item) => (
          <Item key={item.path} item={item} count={counts[item.path]} />
        ))}
      </ul>
      <div className="mt-auto">
        <User user={currentUser} />
      </div>
    </nav>
  )
}
