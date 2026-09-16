import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate, useSearch } from "@tanstack/react-router"
import { useCallback, useEffect, useRef, useState } from "react"

import { type TaskCreate, type TaskPublic, TasksService } from "@/client"
import { Input } from "@/components/ui/input"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

/**
 * Capture: writing a task down costs one field.
 *
 * The old Add Task dialog asked for eight fields up front, nine of them
 * optional, and every one of them editable afterwards in the panel that reads
 * the record. Capture keeps the title and hands the rest to the panel, so
 * creating and editing a task are one interaction instead of two models of the
 * same record.
 *
 * Nothing is written until a title is committed. Opening the panel sends no
 * request, so an accidental open leaves no untitled task in the list, in the
 * activity log, or in the API a bot user reads.
 */

/** A task the panel is about to create, and where it will land. */
export interface CaptureTarget {
  /** The project it goes to, or undefined for the Inbox (FR-05.4). */
  projectId?: string
  /** What to call that project on screen, so the default is never assumed. */
  projectName: string
  /** Set when capturing a subtask: the parent it belongs to. */
  parentId?: string
}

/**
 * Create a task from a committed title.
 *
 * `onCreated` decides what happens next: the panel moves onto the new record,
 * or — for a run of captures — stays open with the field cleared.
 */
export function useTaskCapture(
  target: CaptureTarget,
  onCreated: (task: TaskPublic, stay: boolean) => void,
) {
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  // What a screen reader is told when a task is recorded. A refusal is a
  // toast, like every other failed save in the panel.
  const [announcement, setAnnouncement] = useState("")
  // The titles being written right now, so the same one cannot be sent twice
  // while the first is still going.
  const inFlight = useRef(new Set<string>())

  const mutation = useMutation({
    mutationFn: ({ title }: { title: string; stay: boolean }) => {
      const body: TaskCreate = target.parentId
        ? { title, parent_id: target.parentId }
        : { title, project_id: target.projectId }
      return TasksService.createTask({ body })
    },
    onSuccess: (response, { stay }) => {
      const task = response.data as TaskPublic
      // Success is silent everywhere else in the panel — the record on screen
      // is the receipt. A capture that keeps the field empty has no such
      // receipt, so the one who cannot see the list behind it is told.
      setAnnouncement(`${task.title} created`)
      onCreated(task, stay)
    },
    onError: (error: Error) => {
      setAnnouncement("")
      handleError.call(showErrorToast, error)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
    },
  })

  return {
    /**
     * Create the task, resolving to whether it was accepted. A refusal keeps
     * the title on screen: the words are the reader's, not the request's.
     *
     * A run of captures sends as fast as it is typed — each title is its own
     * task, and holding the second until the first came back would drop it.
     * What is refused is the same title twice over, which is what an
     * impatient second Enter on one thought would file.
     */
    create: async (title: string, stay: boolean) => {
      const trimmed = title.trim()
      if (!trimmed || inFlight.current.has(trimmed)) return false
      inFlight.current.add(trimmed)
      try {
        await mutation.mutateAsync({ title: trimmed, stay })
        return true
      } catch {
        return false
      } finally {
        inFlight.current.delete(trimmed)
      }
    },
    /** Read by a screen reader; the sighted reader has the record itself. */
    announcement,
  }
}

/**
 * The one field capture asks for.
 *
 * Enter commits, the way every text field in the product commits. The chord
 * commits and keeps the field, so a burst of thoughts costs one gesture each.
 * Escape is left to the panel, which cancels: a title that was never committed
 * was never a task.
 */
export function CaptureField({
  label,
  placeholder,
  onCommit,
  staysOpen = false,
  autoFocus,
  className,
}: {
  label: string
  placeholder: string
  /** Resolves to whether the task was created. */
  onCommit: (title: string, stay: boolean) => Promise<boolean>
  /**
   * The field is here for the next title too, whether or not the chord was
   * used — a subtask is captured from the list it joins, and the reader stays
   * in front of it.
   */
  staysOpen?: boolean
  autoFocus?: boolean
  className?: string
}) {
  const [title, setTitle] = useState("")
  const ref = useRef<HTMLInputElement>(null)

  // Focused from here rather than through `autoFocus`, which a sheet's own
  // opening focus would win against. It is claimed twice: on a phone the
  // sidebar is a sheet of its own, and it hands focus back to the button that
  // opened capture as it finishes closing, a moment after this panel arrives.
  useEffect(() => {
    if (!autoFocus) return
    const frame = requestAnimationFrame(() => ref.current?.focus())
    const settled = setTimeout(() => {
      if (document.activeElement !== ref.current) ref.current?.focus()
    }, 350)
    return () => {
      cancelAnimationFrame(frame)
      clearTimeout(settled)
    }
  }, [autoFocus])

  return (
    <Input
      ref={ref}
      aria-label={label}
      placeholder={placeholder}
      value={title}
      onChange={(event) => setTitle(event.target.value)}
      onKeyDown={(event) => {
        if (event.key !== "Enter") return
        event.preventDefault()
        const stay = staysOpen || event.metaKey || event.ctrlKey
        // A capture that stays open clears at once rather than when the
        // request comes back: the next thought is already being typed, and a
        // field that empties late would swallow it. A refusal hands the title
        // back, unless something has been typed in the meantime.
        if (stay) setTitle("")
        void onCommit(title, stay).then((accepted) => {
          if (!accepted && stay) {
            setTitle((current) => (current === "" ? title : current))
          }
        })
      }}
      className={className}
    />
  )
}

/**
 * Where capture happens and how it is left, held in the URL beside the open
 * panel: capture opens over the screen the reader is on, and Back cancels it
 * (The Stay-Put Rule, The Real Address Rule).
 */
export function useCapture() {
  const navigate = useNavigate()
  const search = useSearch({ strict: false }) as {
    task?: string
    capture?: true
    project_id?: string
  }

  const go = useCallback(
    (next: { task?: string; capture?: true }) =>
      navigate({
        to: ".",
        search: (previous: Record<string, unknown>) => ({
          ...previous,
          task: next.task,
          capture: next.capture,
        }),
      }),
    [navigate],
  )

  return {
    taskId: search.task ?? null,
    capturing: search.capture === true,
    /** The project the current list is narrowed to, if it is narrowed at all. */
    filteredProjectId: search.project_id,
    start: useCallback(() => go({ capture: true }), [go]),
    close: useCallback(() => go({}), [go]),
    openTask: useCallback((task: string) => go({ task }), [go]),
  }
}

/** Elements that own the keyboard while they are open. */
const KEYBOARD_OWNERS =
  '[data-slot="dialog-content"],[data-slot="sheet-content"],[data-slot="select-content"],[data-slot="dropdown-menu-content"]'

/**
 * The one key that starts capture from anywhere in the app.
 *
 * Writing a task down is the most frequent and most time-sensitive act in a
 * task tracker, and it was the only one that required a trip to the sidebar.
 * The key stands down wherever something else is listening: a field being
 * typed into, or an open dialog, panel or menu.
 */
export function useCaptureShortcut(start: () => void) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "c") return
      if (event.metaKey || event.ctrlKey || event.altKey) return
      const target = event.target as HTMLElement | null
      if (
        target?.isContentEditable ||
        ["INPUT", "TEXTAREA", "SELECT"].includes(target?.tagName ?? "") ||
        // A select that is closed still listens for letters, to jump to an
        // option by name.
        target?.closest('[role="combobox"],[role="listbox"],[role="menu"]')
      ) {
        return
      }
      if (document.querySelector(KEYBOARD_OWNERS)) return
      event.preventDefault()
      start()
    }

    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [start])
}
