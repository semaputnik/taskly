import * as CheckboxPrimitive from "@radix-ui/react-checkbox"

import type { TaskPublic } from "@/client"
import { Checkbox } from "@/components/ui/checkbox"
import { toastSuccess } from "@/lib/toasts"
import { cn } from "@/lib/utils"
import { StatusMark } from "./status"
import { markName } from "./statuses"
import { useTaskStatus } from "./useTaskWrites"

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
  className?: string
  /** Resizes the drawn mark, for the title that is the status's biggest. */
  markClassName?: string
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
  className,
  markClassName,
}: CompleteTaskProps) {
  const status = useTaskStatus(task, {
    onCompleted: receipt ? completionReceipt(task) : undefined,
  })
  const done = task.status === "done"
  const action = done ? "Reopen task" : "Mark as done"
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
          className={cn(
            // The mark is 18px; the padding takes the target to 26px without
            // moving it off the title's line.
            "focus-visible:ring-ring/50 -m-1 shrink-0 rounded-full p-1 outline-none focus-visible:ring-[3px] disabled:opacity-50",
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
