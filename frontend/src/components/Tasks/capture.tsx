import { useEffect, useRef, useState } from "react"

import { Input } from "@/components/ui/input"

/**
 * Capture: writing a task down in the panel it will be read in.
 *
 * The panel opens as a draft in the task's own layout (ADR-0005): the title,
 * and every property a task has at creation, all editable from the first
 * frame. The draft is held here, in the browser, and becomes the task in one
 * explicit, visible commit — Enter in the title, or Create task — which sends
 * one create request carrying all of it.
 *
 * That one request is what keeps capture's guarantees. Nothing is written
 * while the draft is filled in, so a bot user never sees a half-written task,
 * an accidental open leaves nothing behind, and a task created with a date,
 * a priority and tags is one creation in the activity log rather than a
 * creation followed by edits. Because the draft exists only here, closing one
 * that holds something asks first.
 *
 * Projects and tags, whose only property is a name, keep one-field capture,
 * and so does a subtask added from its parent's Subtasks tab.
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
 * One-field capture, for a subtask added from its parent's Subtasks tab.
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

/** Elements that own the keyboard while they are open. */
const KEYBOARD_OWNERS =
  '[data-slot="dialog-content"],[data-slot="sheet-content"],[data-slot="select-content"],[data-slot="dropdown-menu-content"],[data-slot="popover-content"]'

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
