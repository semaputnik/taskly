import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  ChevronDown,
  CircleCheck,
  CircleDashed,
  Clock3,
  Contrast,
  type LucideIcon,
} from "lucide-react"
import { useState } from "react"

import {
  type SubtaskCompletion,
  type TaskPublic,
  type TaskStatus,
  TasksService,
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"
import { handleError, isOpenSubtasksError } from "@/utils"
import { STATUS_LABELS, STATUSES } from "./statuses"

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
 * Moving one task to a status, from whichever control asked.
 *
 * Moving to done is the one move the API may refuse and ask about: a task
 * with open subtasks needs to be told what happens to them (FR-02.5). Every
 * control — the checkbox, the list's status menu, the panel's status row —
 * goes through here, so that refusal turns into the same prompt wherever it
 * came from. Render `prompt` alongside the control.
 */
export function useTaskStatus(task: TaskPublic) {
  const [isPrompting, setIsPrompting] = useState(false)
  const [announcement, setAnnouncement] = useState("")
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: (body: { status: TaskStatus; subtasks?: SubtaskCompletion }) =>
      TasksService.updateTask({ path: { task_id: task.id }, body }),
    onSuccess: (_, body) => {
      setIsPrompting(false)
      setAnnouncement(`${task.title} moved to ${STATUS_LABELS[body.status]}`)
    },
    onError: (error: Error) => {
      if (isOpenSubtasksError(error)) {
        setIsPrompting(true)
        return
      }
      handleError.call(showErrorToast, error)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      queryClient.invalidateQueries({ queryKey: ["task", task.id] })
      queryClient.invalidateQueries({ queryKey: ["activity"] })
    },
  })

  const change = (status: TaskStatus) => {
    if (status !== task.status) mutation.mutate({ status })
  }

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
        pending={mutation.isPending}
        onChoose={(subtasks) => mutation.mutate({ status: "done", subtasks })}
      />
    </>
  )

  return { change, isPending: mutation.isPending, prompt }
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
