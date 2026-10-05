import { ChevronDown } from "lucide-react"
import type { ReactNode } from "react"

import type { TaskPriority, TaskPublic, TaskStatus } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"
import { PRIORITY_TEXT } from "./priority"
import {
  type MarkTone,
  markName,
  markTone,
  STATUS_LABELS,
  STATUSES,
} from "./statuses"
import { useTaskStatus } from "./useTaskWrites"

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
  className,
}: {
  status: TaskStatus
  priority?: TaskPriority | null
  labelled?: boolean
  className?: string
}) {
  const tone = markTone(status, priority)
  return (
    <svg
      viewBox="0 0 18 18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      className={cn(
        "size-[1.125rem] shrink-0",
        tone ? MARK_TEXT[tone] : "text-foreground",
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

/**
 * The six statuses as menu rows, the current one checked. Shared by every
 * menu that sets a status, so there is one list to read.
 */
export function StatusMenuItems({
  value,
  onChoose,
}: {
  value?: TaskStatus
  onChoose: (status: TaskStatus) => void
}) {
  return (
    <DropdownMenuRadioGroup
      value={value ?? ""}
      onValueChange={(next) => onChoose(next as TaskStatus)}
    >
      {STATUSES.map((status) => (
        <DropdownMenuRadioItem
          key={status}
          value={status}
          className="pointer-coarse:min-h-11"
        >
          <StatusMark status={status} />
          {STATUS_LABELS[status]}
        </DropdownMenuRadioItem>
      ))}
    </DropdownMenuRadioGroup>
  )
}

/**
 * A task's status in the list: mark and label, and the menu that changes it.
 * The mark carries the task's priority as its colour.
 *
 * On a narrow screen the label goes and the mark carries the status alone,
 * still named for assistive technology and still a full-size target.
 */
export function StatusMenu({ task }: { task: TaskPublic }) {
  const status = useTaskStatus(task)
  const label = STATUS_LABELS[task.status]

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            disabled={status.isPending}
            aria-label={`Status: ${markName(task.status, task.priority)}. Change status of ${task.title}`}
            className="-ml-2 size-11 gap-1.5 sm:h-8 sm:w-auto sm:px-2 sm:pointer-coarse:h-11"
          >
            <StatusMark status={task.status} priority={task.priority} />
            <span className="hidden sm:inline">{label}</span>
            <ChevronDown
              className="text-muted-foreground hidden size-3.5 sm:inline"
              aria-hidden
            />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="start"
          // The menu is portalled, but React still bubbles its clicks to the
          // row, which would open the task behind the choice.
          onClick={(event) => event.stopPropagation()}
        >
          <StatusMenuItems value={task.status} onChoose={status.change} />
        </DropdownMenuContent>
      </DropdownMenu>
      {status.prompt}
    </>
  )
}
