import {
  ChevronDown,
  CircleCheck,
  CircleDashed,
  Clock3,
  Contrast,
  type LucideIcon,
} from "lucide-react"

import type { TaskPublic, TaskStatus } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"
import { STATUS_LABELS, STATUSES } from "./statuses"
import { useTaskStatus } from "./useTaskWrites"

export { OPEN_STATUSES, STATUS_LABELS, STATUSES } from "./statuses"

/**
 * One glyph per status, told apart by shape alone (The Four-Glyph Rule):
 * an empty dashed ring, a half-filled one, a ring with a clock hand, and a
 * ring with a check. They stay ink; no status earns a hue.
 */
const STATUS_ICONS: Record<TaskStatus, LucideIcon> = {
  todo: CircleDashed,
  in_progress: Contrast,
  waiting: Clock3,
  done: CircleCheck,
}

/**
 * A status's glyph. Decorative when a label is beside it; given the label as
 * its name when it stands alone.
 */
export function StatusGlyph({
  status,
  labelled = false,
  className,
}: {
  status: TaskStatus
  labelled?: boolean
  className?: string
}) {
  const Icon = STATUS_ICONS[status]
  return (
    <Icon
      className={cn(
        "size-4 shrink-0",
        status === "done" ? "text-muted-foreground" : "text-foreground",
        className,
      )}
      aria-hidden={labelled ? undefined : true}
      aria-label={labelled ? STATUS_LABELS[status] : undefined}
      role={labelled ? "img" : undefined}
    />
  )
}

/**
 * The four statuses as menu rows, the current one checked. Shared by every
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
          <StatusGlyph status={status} />
          {STATUS_LABELS[status]}
        </DropdownMenuRadioItem>
      ))}
    </DropdownMenuRadioGroup>
  )
}

/**
 * A task's status in the list: glyph and label, and the menu that changes it.
 *
 * On a narrow screen the label goes and the glyph carries the status alone,
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
            aria-label={`Status: ${label}. Change status of ${task.title}`}
            className="-ml-2 size-11 gap-1.5 sm:h-8 sm:w-auto sm:px-2 sm:pointer-coarse:h-11"
          >
            <StatusGlyph status={task.status} />
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
