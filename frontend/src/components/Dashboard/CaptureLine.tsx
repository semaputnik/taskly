import { useQuery } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"

import { useRecordPanels } from "@/components/Records/panels"
import { useCaptureTarget } from "@/components/Tasks/capture"
import {
  useTaskCapture,
  useUndoCapture,
} from "@/components/Tasks/useTaskWrites"
import { projectsQuery } from "@/lib/serverState"
import { toastCreated } from "@/lib/toasts"

/**
 * The frameless line at the top of a page that a task is written into: a
 * plus, the field, and the key cap that does the same from anywhere.
 *
 * It writes into the project the page is narrowed to, and says so — "Add a
 * task to Website relaunch…" — and into the Inbox otherwise (FR-05.4,
 * FR-06.15). The day page is narrowed to no project, so there it is always
 * the Inbox.
 *
 * Enter makes the task at once. A title alone is a complete task — Backlog,
 * in the project it is written into, nothing else set — and it is one create
 * request, so nothing is held back for a second step (ADR-0005, amended). The
 * line empties for the next thought and a notice names what was made, with
 * Open (its panel) and Undo (which deletes it; the deletion is restorable
 * from the activity log). A task that needs a day, a priority or another
 * project before it exists is written in the full draft, which the `c` key
 * and the phone's button open.
 */
export function CaptureLine() {
  const panels = useRecordPanels()
  const undo = useUndoCapture()
  const [title, setTitle] = useState("")
  const target = useCaptureTarget()
  // A page narrowed to a project knows the project's name only once the
  // projects have come: words committed before then would go to the Inbox
  // under a line that already says the project's name. The line holds them
  // until it knows where they go.
  const { isPending: projectsPending } = useQuery(projectsQuery())
  const settling = Boolean(panels.filteredProjectId) && projectsPending
  const capture = useTaskCapture(target, (task) =>
    toastCreated(`“${task.title}” created in ${target.projectName}`, {
      open: () => panels.openTask(task.id),
      undo: () => void undo(task),
    }),
  )
  const where = target.projectId ? ` to ${target.projectName}` : ""

  const commit = async () => {
    const typed = title.trim()
    if (!typed || settling) return
    // The line is free for the next thought while this one is on its way.
    setTitle("")
    // The same title again while it is still being written is the one refusal
    // that says nothing: the task is already on its way, so the words do not
    // come back.
    if (capture.isSending(typed)) return
    const created = await capture.create(typed, false)
    // A refusal says why in its own notice; the words come back unless the
    // reader has already started the next ones.
    if (!created) setTitle((now) => now || typed)
  }

  return (
    <label className="text-ink-3 border-rule-strong focus-within:border-ink flex h-10 items-center gap-2.5 border-b transition-colors">
      <Plus aria-hidden className="size-4 shrink-0" strokeWidth={1.5} />
      <input
        type="text"
        aria-label={`Add a task${where}`}
        placeholder={`Add a task${where}…`}
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        onKeyDown={(event) => {
          if (event.key !== "Enter" || event.nativeEvent.isComposing) return
          event.preventDefault()
          void commit()
        }}
        className="text-ink placeholder:text-ink-3 h-full min-w-0 flex-1 bg-transparent text-[15px] outline-none"
      />
      {/* The key works from every screen; the cap is for a keyboard, so a
          touch screen, which has none, goes without it. */}
      <kbd
        aria-hidden
        className="border-rule-strong rounded border px-[5px] font-mono text-[11px] leading-4 pointer-coarse:hidden"
      >
        C
      </kbd>
    </label>
  )
}
