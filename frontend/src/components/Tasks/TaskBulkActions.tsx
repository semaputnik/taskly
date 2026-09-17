import { useMutation, useQueryClient } from "@tanstack/react-query"
import { ChevronDown, Trash2, X } from "lucide-react"
import { useState } from "react"

import {
  type ProjectPublic,
  type TaskBulkUpdate,
  type TaskPriority,
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
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { StatusMenuItems } from "./status"
import { BulkTagPicker } from "./TagPicker"

/**
 * What a selection can be done to, in one bar.
 *
 * Triage is the job only this table can do: a bot user files work all day and
 * a human sweeps it. Sweeping used to mean opening one panel per task. Here a
 * selection is one act — one request, one entry in the log, one thing to undo
 * — and the bar states the size of what is about to change before it changes.
 */

const NONE = "none"

export function TaskBulkActions({
  selected,
  projects,
  matching,
  pageIsWhollySelected,
  onSelectAllMatching,
  onDone,
  onClear,
}: {
  selected: string[]
  projects: ProjectPublic[]
  /** How many tasks the current filters match, in total. */
  matching: number
  pageIsWhollySelected: boolean
  onSelectAllMatching: () => void
  /** Called after a batch lands, so the selection can be released. */
  onDone: () => void
  onClear: () => void
}) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [refused, setRefused] = useState<
    { task_id: string; message: string }[]
  >([])
  const [dueDate, setDueDate] = useState("")

  const change = useMutation({
    mutationFn: ({
      keepSelection: _keep,
      ...body
    }: Omit<TaskBulkUpdate, "task_ids"> & { keepSelection?: boolean }) =>
      TasksService.bulkUpdateTasks({ body: { ...body, task_ids: selected } }),
    onSuccess: ({ data }, { keepSelection }) => {
      setRefused([])
      showSuccessToast(
        `${data.updated} ${data.updated === 1 ? "task" : "tasks"} changed`,
      )
      // Tagging keeps the selection, so several tags go on in one visit.
      if (!keepSelection) onDone()
    },
    onError: (error: Error) => {
      // A batch lands whole or not at all, so a refusal names the rows that
      // stood in the way and leaves everything as it was (story 29).
      const refusals = refusalsOf(error)
      if (refusals) {
        setRefused(refusals)
        return
      }
      handleError.call(showErrorToast, error)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      queryClient.invalidateQueries({ queryKey: ["tags"] })
      queryClient.invalidateQueries({ queryKey: ["activity"] })
    },
  })

  const count = selected.length

  return (
    <div className="bg-card flex flex-col gap-3 rounded-lg border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span aria-live="polite" className="text-sm font-medium">
          {count} selected
        </span>

        <Select
          // Held at no value, so every option — "No priority" included — is
          // a change and fires.
          value=""
          onValueChange={(value) =>
            change.mutate({
              priority: value === NONE ? null : (value as TaskPriority),
            })
          }
        >
          <SelectTrigger className="w-36" aria-label="Set priority">
            <SelectValue placeholder="Priority" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NONE}>No priority</SelectItem>
            {["P1", "P2", "P3", "P4"].map((priority) => (
              <SelectItem key={priority} value={priority}>
                {priority}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value=""
          onValueChange={(project_id) => change.mutate({ project_id })}
        >
          <SelectTrigger className="w-40" aria-label="Move to project">
            <SelectValue placeholder="Move to…" />
          </SelectTrigger>
          <SelectContent>
            {projects.map((project) => (
              <SelectItem key={project.id} value={project.id}>
                {project.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Input
          type="date"
          aria-label="Set due date"
          className="w-40"
          value={dueDate}
          onChange={(event) => {
            setDueDate(event.target.value)
            change.mutate({ due_date: event.target.value || null })
          }}
        />

        <BulkTagPicker
          onAdd={(tag) =>
            change.mutate({ add_tags: [tag], keepSelection: true })
          }
        />

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm">
              Set status
              <ChevronDown className="text-muted-foreground" aria-hidden />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <StatusMenuItems
              onChoose={(status) =>
                // Done takes the subtasks with it, as Complete does: a batch
                // has no one task to ask about.
                change.mutate(
                  status === "done"
                    ? { status, subtasks: "complete" }
                    : { status },
                )
              }
            />
          </DropdownMenuContent>
        </DropdownMenu>

        {/* The shortcut to done, kept beside the menu. */}
        <Button
          variant="outline"
          size="sm"
          onClick={() =>
            change.mutate({ status: "done", subtasks: "complete" })
          }
        >
          Complete
        </Button>

        <DeleteSelection
          count={count}
          selected={selected}
          onDone={onDone}
          onRefused={setRefused}
        />

        <Button variant="ghost" size="sm" className="ml-auto" onClick={onClear}>
          <X />
          Clear selection
        </Button>
      </div>

      {pageIsWhollySelected && matching > selected.length && (
        <p className="text-muted-foreground text-sm">
          Every task on this page is selected.{" "}
          <button
            type="button"
            onClick={onSelectAllMatching}
            className="text-foreground font-medium underline-offset-4 hover:underline"
          >
            Select all {matching} tasks matching these filters
          </button>
          {matching > 500 && " (the first 500 of them)"}
        </p>
      )}

      {refused.length > 0 && (
        <div className="border-destructive/40 text-sm rounded-md border p-3">
          <p className="font-medium">
            Nothing was changed: {refused.length}{" "}
            {refused.length === 1 ? "task" : "tasks"} stood in the way.
          </p>
          <ul className="text-muted-foreground mt-1 list-disc pl-5">
            {refused.map((refusal) => (
              <li key={refusal.task_id}>{refusal.message}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function DeleteSelection({
  count,
  selected,
  onDone,
  onRefused,
}: {
  count: number
  selected: string[]
  onDone: () => void
  onRefused: (refusals: { task_id: string; message: string }[]) => void
}) {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const remove = useMutation({
    mutationFn: (delete_subtasks: boolean) =>
      TasksService.bulkDeleteTasks({
        body: { task_ids: selected, delete_subtasks },
      }),
    onSuccess: ({ data }) => {
      showSuccessToast(
        `${data.deleted} ${data.deleted === 1 ? "task" : "tasks"} deleted`,
      )
      setIsOpen(false)
      onDone()
    },
    onError: (error: Error) => {
      const refusals = refusalsOf(error)
      if (refusals) {
        onRefused(refusals)
        setIsOpen(false)
        return
      }
      handleError.call(showErrorToast, error)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      queryClient.invalidateQueries({ queryKey: ["activity"] })
    },
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <Button
        variant="outline"
        size="sm"
        className="text-muted-foreground hover:text-destructive"
        onClick={() => setIsOpen(true)}
      >
        <Trash2 />
        Delete
      </Button>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            Delete {count} {count === 1 ? "task" : "tasks"}?
          </DialogTitle>
          <DialogDescription>
            Any subtasks they have go with them. The deletion is recorded in
            your activity log as one act, so the whole batch can be restored
            from there.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={remove.isPending}>
              Cancel
            </Button>
          </DialogClose>
          <LoadingButton
            variant="destructive"
            loading={remove.isPending}
            onClick={() => remove.mutate(true)}
          >
            Delete
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** The tasks a batch refused, when that is what came back. */
function refusalsOf(
  error: Error,
): { task_id: string; message: string }[] | null {
  const detail = (error as { response?: { data?: { detail?: unknown } } })
    .response?.data?.detail as
    | { code?: string; refusals?: { task_id: string; message: string }[] }
    | undefined
  return detail?.code === "bulk_refused" ? (detail.refusals ?? []) : null
}
