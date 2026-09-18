import { Link as RouterLink } from "@tanstack/react-router"
import { ArrowRight } from "lucide-react"

import { cn } from "@/lib/utils"

/** How many rows a band shows before it hands off to the task list. */
export const PREVIEW_ROWS = 5

/**
 * A band of rows under its own label. Group headers borrow the table's
 * uppercase micro type because that is exactly what they are — a header over
 * a set of rows — and inventing a second treatment for the same job would
 * read as an inconsistency, not a distinction.
 */
export function Group({
  label,
  count,
  tone = "default",
  children,
}: {
  label: string
  count: number
  tone?: "default" | "alert"
  children: React.ReactNode
}) {
  return (
    <section>
      <h2 className="bg-muted/50 flex items-center gap-2 border-b px-4 py-2.5 text-xs font-semibold tracking-wider uppercase">
        <span className={cn(tone === "alert" && "text-destructive")}>
          {label}
        </span>
        <span className="text-muted-foreground font-normal tabular-nums">
          {count}
        </span>
      </h2>
      {children}
    </section>
  )
}

/** The row that ends a band too long to show, handing off to the list. */
export function MoreLink({
  count,
  label,
  search,
}: {
  count: number
  /** Said instead of the count when there is nothing more to count. */
  label?: string
  search: Record<string, unknown>
}) {
  return (
    <RouterLink
      to="/tasks"
      search={search}
      className="hover:bg-muted/50 flex items-center justify-between gap-2 border-b px-4 py-3 text-sm transition-colors last:border-b-0"
    >
      <span className="text-muted-foreground">
        {count > 0 ? `${count} more` : label}
      </span>
      <ArrowRight className="text-muted-foreground size-4" aria-hidden />
    </RouterLink>
  )
}
