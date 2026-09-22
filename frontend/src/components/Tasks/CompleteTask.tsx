import type { TaskPublic } from "@/client"
import { Checkbox } from "@/components/ui/checkbox"
import { toastSuccess } from "@/lib/toasts"
import { cn } from "@/lib/utils"
import { PRIORITY_CHECK, priorityTone } from "./priority"
import { useTaskStatus } from "./useTaskWrites"

interface CompleteTaskProps {
  task: TaskPublic
  /**
   * Carry the task's priority on the checkbox itself — its ring in the
   * priority's hue — for rows that have no priority column (the compact row).
   * The priority is then part of the checkbox's name, since the ring alone
   * says nothing to a screen reader.
   */
  showPriority?: boolean
  /**
   * This checkbox's row leaves the list when it is ticked, so confirm the
   * move and offer the way back.
   *
   * Everywhere else the value on screen is the receipt and the write is
   * silent. In a list of open work there is no value left on screen to be
   * the receipt — the row is gone — so the notice takes its place rather
   * than adding to it.
   */
  receipt?: boolean
  className?: string
}

/**
 * The round checkbox: the fastest way to close a task, whatever status it is
 * in (FR-01.5).
 *
 * It is checked only when the task is done. Checking moves the task to done,
 * through the same path as every other status control, so open subtasks raise
 * the same prompt (FR-02.5). Unchecking returns it to to do: undoing a close
 * cannot know which open status the task had before.
 */
export function CompleteTask({
  task,
  showPriority = false,
  receipt = false,
  className,
}: CompleteTaskProps) {
  const status = useTaskStatus(task)
  const done = task.status === "done"
  const tone = showPriority ? priorityTone(task.priority) : null
  const action = done ? "Reopen task" : "Mark as done"

  const tick = async (checked: boolean) => {
    const moved = await status.change(checked ? "done" : "todo")
    if (!receipt || !moved || !checked) return
    toastSuccess(`“${task.title}” done`, {
      label: "Undo",
      // Back to to do, as reopening always is: undoing a close cannot know
      // which open status the task held before it. `reopen` rather than
      // `change`, because this notice outlives the row it came from and
      // still holds the task as it was before the move.
      onClick: () => void status.reopen(),
    })
  }

  return (
    <>
      <Checkbox
        // Round: a square check in this table selects a row, and closing a
        // task is neither a selection nor a value — it is the task's state.
        className={cn("rounded-full", tone && PRIORITY_CHECK[tone], className)}
        checked={done}
        disabled={status.isPending}
        onCheckedChange={(checked) => void tick(checked === true)}
        aria-label={
          showPriority && task.priority
            ? `${action}, priority ${task.priority}`
            : action
        }
      />
      {status.prompt}
    </>
  )
}
