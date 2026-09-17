import type { TaskPublic } from "@/client"
import { Checkbox } from "@/components/ui/checkbox"
import { useTaskStatus } from "./useTaskWrites"

interface CompleteTaskProps {
  task: TaskPublic
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
export function CompleteTask({ task }: CompleteTaskProps) {
  const status = useTaskStatus(task)
  const done = task.status === "done"

  return (
    <>
      <Checkbox
        // Round: a square check in this table selects a row, and closing a
        // task is neither a selection nor a value — it is the task's state.
        className="rounded-full"
        checked={done}
        disabled={status.isPending}
        onCheckedChange={(checked) =>
          status.change(checked === true ? "done" : "todo")
        }
        aria-label={done ? "Reopen task" : "Mark as done"}
      />
      {status.prompt}
    </>
  )
}
