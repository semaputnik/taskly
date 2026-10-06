import { textLink } from "@/components/Dashboard/shared"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

/**
 * The small parts the work sections of a record's column share (a project's
 * and a tag's open tasks): the way on to the whole list, the quiet line for
 * nothing, the placeholder while it loads, and a property's action.
 */

/** "N more in the list →", under a preview that stops at a handful of lines. */
export const more = cn(
  textLink,
  "text-ink-3 hover:text-ink inline-block pt-2 text-[13px]",
)

/** A property's action, in words, as the mock sets it: ink, 13.5px, medium. */
export const act = cn(
  textLink,
  "text-ink text-[13.5px] font-medium whitespace-nowrap disabled:opacity-50 pointer-coarse:-my-3 pointer-coarse:py-3",
)

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-ink-3 pt-2 text-sm text-pretty italic">{children}</p>
  )
}

export function Pending() {
  return (
    <div className="flex flex-col gap-2 pt-3" aria-hidden>
      {Array.from({ length: 3 }).map((_, index) => (
        <Skeleton key={index} className="h-8 w-full" />
      ))}
    </div>
  )
}
