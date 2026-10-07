import * as CheckboxPrimitive from "@radix-ui/react-checkbox"

import type { TaskPublic } from "@/client"
import { Checkbox } from "@/components/ui/checkbox"
import { toastSuccess } from "@/lib/toasts"
import { cn } from "@/lib/utils"
import { STATUS_LABELS, StatusMark } from "./status"
import { markName } from "./statuses"
import { useTaskStatus } from "./useTaskWrites"

/**
 * The tip over a status mark: the status's name on a raised chip, above the
 * mark and level with its left edge, where the column's gutter is clear. It
 * has left the page plane, so it takes the menus' shadow. It shows after a
 * short pause, on a hovering pointer (never a touch, which has no hover) and
 * on keyboard focus.
 */
export const MARK_TIP = cn(
  "relative after:pointer-events-none after:absolute after:bottom-full after:left-0 after:z-30 after:mb-1.5 after:rounded-md after:border after:bg-popover after:px-2 after:py-1 after:text-xs after:leading-none after:font-normal after:whitespace-nowrap after:text-popover-foreground after:shadow-md after:opacity-0 after:transition-opacity after:content-[attr(data-tip)]",
  "hover:after:opacity-100 hover:after:delay-500 focus-visible:after:opacity-100",
)

interface CompleteTaskProps {
  task: TaskPublic
  /**
   * Draw the control as the task's status mark, in its priority's colour,
   * rather than as a round checkbox — for rows that have neither a status nor
   * a priority column (the compact row). The status and priority are then
   * part of the control's name, since the shape and colour alone say nothing
   * to a screen reader.
   */
  asMark?: boolean
  /** With `asMark`, the task is overdue: see `StatusMark`'s `late`. */
  late?: boolean
  /**
   * This control's row leaves the list when it is ticked, so confirm the
   * move and offer the way back.
   *
   * Everywhere else the value on screen is the receipt and the write is
   * silent. In a list of open work there is no value left on screen to be
   * the receipt — the row is gone — so the notice takes its place rather
   * than adding to it.
   */
  receipt?: boolean
  /** Say the result in the column's bar, for the control of the open task. */
  announce?: boolean
  className?: string
  /** Resizes the drawn mark, for the title that is the status's biggest. */
  markClassName?: string
  /**
   * Names the status in a small tip over the mark, on hover and on keyboard
   * focus, for a line whose mark has no label beside it. The tip is drawn
   * from an attribute by CSS, so it is not in the page's text: the control's
   * own name already says the status, and says it once.
   */
  tip?: boolean
}

/**
 * The notice that confirms a task closed from a list it then leaves, and
 * offers the way back (ADR-0006). For `useTaskStatus`'s `onCompleted`.
 */
export function completionReceipt(task: TaskPublic) {
  return (reopen: () => Promise<boolean>) =>
    toastSuccess(`“${task.title}” done`, {
      label: "Undo",
      // Back to to do, as reopening always is: undoing a close cannot know
      // which open status the task held before it. `reopen` rather than
      // `change`, because this notice outlives the row it came from and
      // still holds the task as it was before the move.
      onClick: () => void reopen(),
    })
}

/**
 * The fastest way to close a task, whatever status it is in (FR-01.5).
 *
 * It is checked only when the task is done. Checking moves the task to done,
 * through the same path as every other status control, so open subtasks raise
 * the same prompt (FR-02.5). Unchecking returns it to to do: undoing a close
 * cannot know which open status the task had before.
 */
export function CompleteTask({
  task,
  asMark = false,
  late = false,
  receipt = false,
  announce = false,
  className,
  markClassName,
  tip = false,
}: CompleteTaskProps) {
  const status = useTaskStatus(task, {
    onCompleted: receipt ? completionReceipt(task) : undefined,
    announce,
  })
  const done = task.status === "done"
  const action = done ? "Reopen task" : "Mark done"
  const toggle = (checked: boolean) =>
    void status.change(checked ? "done" : "todo")

  if (asMark) {
    return (
      <>
        {/* A checkbox in every way but its look: ticking it is the same act
            as ticking the round one, and it says so to assistive technology. */}
        <CheckboxPrimitive.Root
          checked={done}
          disabled={status.isPending}
          onCheckedChange={(checked) => toggle(checked === true)}
          aria-label={`${action} (${markName(task.status, task.priority)})`}
          data-tip={tip ? STATUS_LABELS[task.status] : undefined}
          className={cn(
            // The padding takes the target to 26px without moving the mark off
            // the title's line; a caller on a thumb widens it (see `className`).
            "focus-visible:ring-ring/50 -m-1 shrink-0 rounded-full p-1 outline-none focus-visible:ring-[3px] disabled:opacity-50",
            tip && MARK_TIP,
            className,
          )}
        >
          <StatusMark
            status={task.status}
            priority={task.priority}
            late={late}
            className={markClassName}
          />
        </CheckboxPrimitive.Root>
        {status.prompt}
      </>
    )
  }

  return (
    <>
      <Checkbox
        // Round: a square check in this table selects a row, and closing a
        // task is neither a selection nor a value — it is the task's state.
        className={cn("rounded-full", className)}
        checked={done}
        disabled={status.isPending}
        onCheckedChange={(checked) => toggle(checked === true)}
        aria-label={action}
      />
      {status.prompt}
    </>
  )
}
