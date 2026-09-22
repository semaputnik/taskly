import { useRef, useState } from "react"

import type {
  DueDateScope,
  SubtaskCompletion,
  TaskBulkUpdate,
  TaskPublic,
  TaskStatus,
  TaskUpdate,
} from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import useAuth from "@/hooks/useAuth"
import type { BatchRefusal } from "@/lib/apiErrors"
import { useReportChange } from "@/lib/serverState"
import { toastError, toastSuccess } from "@/lib/toasts"
import type { CaptureTarget } from "./capture"
import { draftToCreate, emptyDraft, type TaskDraft } from "./draft"
import { DueDateScopeDialog } from "./recurrence"
import { STATUS_LABELS } from "./statuses"
import {
  bulkDelete,
  bulkUpdate,
  createTask,
  deleteTask,
  type Outcome,
  type Report,
  setStatus,
  updateTask,
} from "./writes"

/**
 * The task writes, as controls use them.
 *
 * One feedback policy for all of them: an edit in a panel is silent — the
 * value on screen is the receipt — while a batch and a destructive act
 * confirm with a toast. A failure always raises one. The prompts a write can
 * need (open subtasks, a due date's scope) are rendered by the hook that
 * needs them, so no control has to remember to.
 */

/** Run writes, counting the ones in flight and toasting any failure. */
function useWrites() {
  const report = useReportChange()
  const [inFlight, setInFlight] = useState(0)

  async function run<T>(write: (report: Report) => Promise<Outcome<T>>) {
    setInFlight((count) => count + 1)
    try {
      const outcome = await write(report)
      if (!outcome.saved && outcome.reason === "failed") {
        toastError(outcome.error)
      }
      return outcome
    } finally {
      setInFlight((count) => count - 1)
    }
  }

  return { run, isPending: inFlight > 0 }
}

/**
 * Saving fields of a task, from wherever it is being edited.
 *
 * `save` resolves to whether the change was saved, so a field that was
 * refused keeps what was typed. An omitted key means "leave unchanged" to the
 * API, so a cleared field must be sent as `null` rather than dropped. Render
 * `prompt` alongside: a moved date on a recurring task waits there for its
 * scope, and `save` resolves once it is chosen or the question is dismissed.
 */
export function useTaskUpdate(task: TaskPublic) {
  const { run, isPending } = useWrites()
  const [asking, setAsking] = useState<TaskUpdate | null>(null)
  const settle = useRef<(saved: boolean) => void>(() => {})

  const save = async (body: TaskUpdate): Promise<boolean> => {
    const outcome = await run((report) => updateTask(report, task, body))
    if (outcome.saved || outcome.reason !== "needs scope") return outcome.saved
    return new Promise<boolean>((resolve) => {
      settle.current = resolve
      setAsking(body)
    })
  }

  const answer = async (scope: DueDateScope | null) => {
    const body = asking
    const resolve = settle.current
    if (!body) return
    if (scope === null) {
      setAsking(null)
      resolve(false)
      return
    }
    const outcome = await run((report) => updateTask(report, task, body, scope))
    setAsking(null)
    resolve(outcome.saved)
  }

  const prompt = (
    <DueDateScopeDialog
      open={asking !== null}
      onOpenChange={(open) => !open && answer(null)}
      onChoose={answer}
      pending={isPending}
    />
  )

  return { save, isPending, prompt }
}

/**
 * Moving one task to a status, from whichever control asked.
 *
 * Moving to done is the one move the API may refuse and ask about: a task
 * with open subtasks needs to be told what happens to them (FR-02.5). Every
 * control goes through here, so that refusal turns into the same prompt
 * wherever it came from. Render `prompt` alongside the control.
 */
export function useTaskStatus(
  task: TaskPublic,
  {
    onCompleted,
  }: {
    /**
     * The task reached done, by whichever path — the control directly, or
     * the prompt that asks about its open subtasks first. It is handed
     * `reopen` so a receipt can offer the way back without having to reach
     * for the hook it is being built inside.
     */
    onCompleted?: (reopen: () => Promise<boolean>) => void
  } = {},
) {
  const { run, isPending } = useWrites()
  const [isPrompting, setIsPrompting] = useState(false)
  const [announcement, setAnnouncement] = useState("")

  const move = async (status: TaskStatus, subtasks?: SubtaskCompletion) => {
    const outcome = await run((report) =>
      setStatus(report, task, status, subtasks),
    )
    if (outcome.saved) {
      setIsPrompting(false)
      setAnnouncement(`${task.title} moved to ${STATUS_LABELS[status]}`)
      // Here rather than at the control, so a task closed through the
      // subtasks prompt is confirmed exactly like one closed in a click.
      if (status === "done") onCompleted?.(reopen)
    } else if (outcome.reason === "open subtasks") {
      setIsPrompting(true)
    }
    return outcome.saved
  }

  // Resolves to whether the task actually moved, so a caller whose row is
  // about to leave the screen can confirm it — and offer the way back — only
  // once the move has landed.
  const change = async (status: TaskStatus): Promise<boolean> => {
    if (status === task.status) return false
    return move(status)
  }

  // Reopen, whatever this control last knew the task's status to be.
  //
  // `change` declines to write when the task already holds the status asked
  // for, which is right for a control reading a live task and wrong for one
  // that has outlived it. The notice raised when a task leaves a list of open
  // work is exactly that: it holds the task as it was *before* the move, so
  // asking `change` to put it back to to do would compare to do against to
  // do and write nothing at all.
  const reopen = () => move("todo")

  const prompt = (
    <>
      {/* The change happens in a list or behind a menu that has closed, so
          it is said as well as shown. */}
      <output aria-live="polite" className="sr-only">
        {announcement}
      </output>
      <SubtasksPrompt
        title={task.title}
        open={isPrompting}
        onOpenChange={setIsPrompting}
        pending={isPending}
        onChoose={(subtasks) => void move("done", subtasks)}
      />
    </>
  )

  return { change, reopen, isPending, prompt }
}

function SubtasksPrompt({
  title,
  open,
  onOpenChange,
  pending,
  onChoose,
}: {
  title: string
  open: boolean
  onOpenChange: (open: boolean) => void
  pending: boolean
  onChoose: (subtasks: SubtaskCompletion) => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-md"
        // Portalled out of a clickable row, whose click would open the task.
        onClick={(event) => event.stopPropagation()}
      >
        <DialogHeader>
          <DialogTitle>This task has open subtasks</DialogTitle>
          <DialogDescription>
            “{title}” still has subtasks that are not done. Choose what happens
            to them.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="sm:flex-col sm:gap-2">
          <Button
            variant="outline"
            disabled={pending}
            onClick={() => onChoose("complete")}
          >
            Mark the subtasks done too
          </Button>
          <Button
            variant="outline"
            disabled={pending}
            onClick={() => onChoose("leave_uncompleted")}
          >
            Leave the subtasks as they are
          </Button>
          <DialogClose asChild>
            <Button variant="ghost" disabled={pending}>
              Cancel
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/**
 * Create a task from a committed draft, or from a title alone.
 *
 * `onCreated` decides what happens next: the panel moves onto the new record,
 * or — for a run of captures — stays open with the field cleared.
 */
export function useTaskCapture(
  target: CaptureTarget,
  onCreated: (task: TaskPublic, stay: boolean) => void,
) {
  const { run } = useWrites()
  const { user: currentUser } = useAuth()
  // What a screen reader is told when a task is recorded. A refusal is a
  // toast, like every other failed save in the panel.
  const [announcement, setAnnouncement] = useState("")
  // The titles being written right now, so the same one cannot be sent twice
  // while the first is still going.
  const inFlight = useRef(new Set<string>())

  return {
    /**
     * Create the task, resolving to whether it was accepted. A refusal keeps
     * the draft on screen: the words are the reader's, not the request's.
     *
     * A run of captures sends as fast as it is typed — each title is its own
     * task, and holding the second until the first came back would drop it.
     * What is refused is the same title twice over, which is what an
     * impatient second Enter on one thought would file.
     */
    create: async (input: string | TaskDraft, stay: boolean) => {
      const draft =
        typeof input === "string"
          ? { ...emptyDraft(target), title: input }
          : input
      const trimmed = draft.title.trim()
      if (!trimmed || inFlight.current.has(trimmed)) return false
      inFlight.current.add(trimmed)
      try {
        const outcome = await run((report) =>
          createTask(report, draftToCreate(draft, target, currentUser?.id)),
        )
        if (!outcome.saved) {
          setAnnouncement("")
          return false
        }
        // Success is silent everywhere else in the panel — the record on
        // screen is the receipt. A capture that keeps the field empty has no
        // such receipt, so the one who cannot see the list behind it is told.
        setAnnouncement(`${outcome.data.title} created`)
        onCreated(outcome.data, stay)
        return true
      } finally {
        inFlight.current.delete(trimmed)
      }
    },
    /** Read by a screen reader; the sighted reader has the record itself. */
    announcement,
  }
}

/**
 * Deleting one task. A task with subtasks is refused until the cascade is
 * confirmed: `remove` resolves to "has subtasks" for the caller to warn.
 */
export function useTaskDelete(task: TaskPublic) {
  const { run, isPending } = useWrites()

  const remove = async (withSubtasks: boolean) => {
    const outcome = await run((report) =>
      deleteTask(report, task, withSubtasks),
    )
    if (outcome.saved) {
      toastSuccess(
        `“${task.title}” was deleted. It can be restored from the activity log.`,
      )
    }
    return outcome
  }

  return { remove, isPending }
}

/**
 * Changing or deleting a selection as one act. `known` are the selected
 * tasks this screen has seen, which lets a batch the server would refuse be
 * refused before it is sent. A refusal lands in `refused`, naming the tasks
 * that stood in the way.
 */
export function useBulkTaskWrites(selected: string[], known: TaskPublic[]) {
  const { run, isPending } = useWrites()
  const [refused, setRefused] = useState<BatchRefusal[]>([])

  const settle = <T,>(outcome: Outcome<T>, success: string) => {
    if (outcome.saved) {
      setRefused([])
      toastSuccess(success)
    } else if (outcome.reason === "batch") {
      // A batch lands whole or not at all, so a refusal names the rows that
      // stood in the way and leaves everything as it was (story 29).
      setRefused(outcome.refusals)
    }
    return outcome.saved
  }

  const count = (n: number | undefined, done: string) =>
    `${n ?? 0} ${n === 1 ? "task" : "tasks"} ${done}`

  return {
    refused,
    isPending,
    change: async (body: Omit<TaskBulkUpdate, "task_ids">) => {
      const outcome = await run((report) =>
        bulkUpdate(report, selected, known, body),
      )
      return settle(
        outcome,
        count(outcome.saved ? outcome.data.updated : 0, "changed"),
      )
    },
    /**
     * Delete the selection. `settled` says the question is answered: deleted,
     * or refused with the tasks in the way listed. A failure that says
     * nothing about the tasks leaves it open.
     */
    remove: async () => {
      const outcome = await run((report) => bulkDelete(report, selected))
      const deleted = settle(
        outcome,
        count(outcome.saved ? outcome.data.deleted : 0, "deleted"),
      )
      return {
        deleted,
        settled: deleted || (!outcome.saved && outcome.reason === "batch"),
      }
    },
  }
}
