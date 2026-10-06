import type { ReactNode } from "react"

import type { TaskPriority, TaskStatus } from "@/client"
import { cn } from "@/lib/utils"
import { PRIORITY_TEXT } from "./priority"
import { type MarkTone, markName, markTone } from "./statuses"

export { OPEN_STATUSES, STATUS_LABELS, STATUSES } from "./statuses"

/**
 * One mark per status, told apart by shape alone so they read in greyscale:
 * a dashed ring, a solid ring, a half-filled ring, a dot in a ring, an eye,
 * and a filled check. Drawn on an 18-unit grid with a 1.5 stroke in
 * `currentColor`, so the colour is the priority's and never the status's.
 */
const STATUS_SHAPES: Record<TaskStatus, ReactNode> = {
  backlog: <circle cx="9" cy="9" r="7" strokeDasharray="2.6 2.4" />,
  todo: <circle cx="9" cy="9" r="7" />,
  in_progress: (
    <>
      <circle cx="9" cy="9" r="7" />
      <path d="M9 4.5a4.5 4.5 0 0 1 0 9z" fill="currentColor" stroke="none" />
    </>
  ),
  review: (
    <>
      <circle cx="9" cy="9" r="7" />
      <circle cx="9" cy="9" r="2.6" fill="currentColor" stroke="none" />
    </>
  ),
  waiting: (
    <>
      <path
        d="M1.8 9c1.9-3.4 4.3-5 7.2-5s5.3 1.6 7.2 5c-1.9 3.4-4.3 5-7.2 5S3.7 12.4 1.8 9z"
        strokeLinejoin="round"
      />
      <circle cx="9" cy="9" r="2.4" />
      <circle cx="9" cy="9" r=".9" fill="currentColor" stroke="none" />
    </>
  ),
  done: (
    <>
      <circle cx="9" cy="9" r="7" fill="currentColor" stroke="none" />
      {/* Cut out of the fill in the colour of the sheet rows sit on, so it reads
          on the green in either theme. */}
      <path
        d="M5.8 9.3l2.2 2.2 4.3-4.6"
        stroke="var(--card)"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </>
  ),
}

/**
 * The colour each tone gives a mark; a mark with no tone is ink. The priority
 * hues clear 4.5:1 on both grounds in both themes (see `--priority-*` in
 * `index.css`). Done is the palette's one green, `--done`, checked there
 * against every ground in both themes.
 */
const MARK_TEXT: Record<MarkTone, string> = {
  ...PRIORITY_TEXT,
  done: "text-done",
}

/**
 * A status's mark. Given the task's priority, it takes the priority's colour;
 * without one, as in a menu of statuses, it stands for the status alone.
 *
 * Decorative when a label is beside it; given the status, and the priority,
 * as its name when it stands alone.
 */
export function StatusMark({
  status,
  priority,
  labelled = false,
  late = false,
  className,
}: {
  status: TaskStatus
  priority?: TaskPriority | null
  labelled?: boolean
  /**
   * Set on the line of an overdue task: its due day is already in the alert
   * red, so a P1 mark, which is that same red, is set in ink instead, and red
   * is said once on the line. The priority is still in the mark's name.
   */
  late?: boolean
  className?: string
}) {
  const tone = markTone(status, priority)
  const colour = late && tone === "p1" ? null : tone
  return (
    <svg
      viewBox="0 0 18 18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      className={cn(
        "size-[1.125rem] shrink-0",
        colour ? MARK_TEXT[colour] : "text-foreground",
        className,
      )}
      aria-hidden={labelled ? undefined : true}
      aria-label={labelled ? markName(status, priority) : undefined}
      role={labelled ? "img" : undefined}
    >
      {STATUS_SHAPES[status]}
    </svg>
  )
}
