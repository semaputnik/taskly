import { Link as RouterLink } from "@tanstack/react-router"
import { ArrowRight, Tag as TagGlyph } from "lucide-react"

import type { TagPublic } from "@/client"
import { countLink } from "@/components/Dashboard/shared"
import { recordLink, useIsOpen } from "@/components/Records/panels"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import { archivedNote } from "./counts"
import { createdBy } from "./words"

/**
 * A tag as a line: its glyph, its name, who made it, and at the right the
 * count of open tasks as the way into the task list narrowed to the tag. The
 * count is the list's own, so the number on the link is the number the list
 * shows (FR-01.26); what it leaves out is said beside the maker.
 *
 * The name opens the column, as a task's title does, rather than the whole
 * line, so a list of records behaves as one.
 */
export function TagLine({ tag }: { tag: TagPublic }) {
  const open = useIsOpen("tag", tag.id)
  const count = tag.task_count ?? 0
  const archived = archivedNote(tag)

  return (
    <li
      className={cn(
        "border-rule hover:row-tint grid grid-cols-[14px_minmax(0,1fr)_auto] items-start gap-x-3 border-b py-2.5 transition-colors last:border-b-0",
        open && "row-tint",
      )}
    >
      <TagGlyph
        aria-hidden
        className="text-ink-3 mt-[5px] size-3.5"
        strokeWidth={1.4}
      />
      <div className="min-w-0">
        <RouterLink
          {...recordLink("tag", tag.id)}
          className="focus-visible:ring-ring/50 block truncate rounded-sm leading-snug font-medium whitespace-pre underline-offset-4 outline-none hover:underline focus-visible:ring-[3px]"
        >
          {tag.name}
        </RouterLink>
        <p className="text-ink-3 mt-px flex flex-wrap gap-x-3 text-[12.5px] leading-tight">
          <span>{createdBy(tag)}</span>
          {archived && <span>{archived}</span>}
        </p>
      </div>
      {count > 0 ? (
        <RouterLink
          to="/tasks"
          search={{ tag: tag.name }}
          aria-label={`${count} open, open the list of ${tag.name}`}
          className={countLink}
        >
          {count} open
          <ArrowRight aria-hidden className="size-3" strokeWidth={1.5} />
        </RouterLink>
      ) : (
        <span className="text-ink-3 text-[13.5px] whitespace-nowrap">
          No open tasks
        </span>
      )}
    </li>
  )
}

/** A line while its tag is on its way. */
export function TagLinePending() {
  return (
    <div className="border-rule grid grid-cols-[14px_minmax(0,1fr)_auto] gap-x-3 border-b py-2.5 last:border-b-0">
      <Skeleton className="mt-[5px] size-3.5" />
      <div className="flex flex-col gap-1.5">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-3 w-24" />
      </div>
      <Skeleton className="h-3 w-16" />
    </div>
  )
}
