import { Plus } from "lucide-react"
import { useState } from "react"

import { useRecordPanels } from "@/components/Records/panels"

/**
 * The frameless line at the top of the day page that a task is written
 * into: a plus, the field, and the key cap that does the same from anywhere.
 *
 * It is the start of capture, not capture itself. Enter opens the capture
 * panel with whatever was typed as the draft's title, so the rest of the
 * task — its day, priority, project — is set in the same draft as from the
 * `c` key or the floating button, and the task is still created in one
 * commit (ADR-0005). The line then empties, ready for the next thought.
 */
export function CaptureLine() {
  const { capture } = useRecordPanels()
  const [title, setTitle] = useState("")

  return (
    <label className="text-ink-3 border-rule-strong focus-within:border-ink flex h-10 items-center gap-2.5 border-b transition-colors">
      <Plus aria-hidden className="size-4 shrink-0" strokeWidth={1.5} />
      <input
        type="text"
        aria-label="Add a task"
        placeholder="Add a task…"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        onKeyDown={(event) => {
          if (event.key !== "Enter" || event.nativeEvent.isComposing) return
          event.preventDefault()
          capture("task", title.trim() || undefined)
          setTitle("")
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
