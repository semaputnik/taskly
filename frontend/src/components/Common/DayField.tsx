import { CalendarDays, X } from "lucide-react"
import { useRef, useSyncExternalStore } from "react"

import { Button } from "@/components/ui/button"
import { formatDay } from "@/lib/dates"
import { cn } from "@/lib/utils"

/**
 * A stored day, written the product's way, with the browser's own picker to
 * change it.
 *
 * A native date field writes its value in the browser's interface language,
 * which need not be the locale the rest of the page is written in — so the
 * same due date could read "01.09.2026" in the panel and "09/01/2026" in the
 * table beside it. Here the day is always shown by `formatDay`, and the native
 * field only does the picking (One Way to Write a Date).
 *
 * With a mouse, the button opens the picker by script. A touch screen gets the
 * native field itself, laid invisibly over the button, because iOS opens no
 * date picker from script — neither `showPicker` nor `focus` on a field that
 * is not the one touched — so there the finger has to land on the real field.
 */
const COARSE = "(pointer: coarse)"

/** Whether the reader points with a finger, following changes as they happen. */
function useCoarsePointer(): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const query = window.matchMedia(COARSE)
      query.addEventListener("change", onChange)
      return () => query.removeEventListener("change", onChange)
    },
    () => window.matchMedia(COARSE).matches,
    () => false,
  )
}

export function DayField({
  id,
  label,
  value,
  onChange,
  className,
}: {
  id?: string
  /** What the day is, for the control's name: "Due date". */
  label: string
  value: string | null | undefined
  onChange: (day: string | null) => void
  className?: string
}) {
  const picker = useRef<HTMLInputElement>(null)
  // On a touch screen the native field is the control — for a finger and for
  // a screen reader alike, since VoiceOver's activation is no more able than a
  // script to open iOS's picker from the button — and the button is only what
  // is seen.
  const coarse = useCoarsePointer()
  const name = value ? `${label}: ${formatDay(value)}` : `${label}: not set`

  const open = () => {
    const input = picker.current
    if (!input) return
    try {
      input.showPicker()
    } catch {
      // A browser without `showPicker` still lets the field take focus.
      input.focus()
    }
  }

  return (
    <div className="flex items-center gap-1">
      {/* Button and field share a box of their own, so the field covers the
          button and never the clear control beside it. */}
      <div className="relative min-w-0 flex-1">
        <button
          id={id}
          type="button"
          aria-label={coarse ? undefined : name}
          aria-hidden={coarse || undefined}
          tabIndex={coarse ? -1 : undefined}
          onClick={open}
          className={cn(
            "border-input focus-visible:border-ring focus-visible:ring-ring/50 flex h-9 w-full min-w-0 items-center justify-between gap-2 rounded-md border px-3 text-left text-base outline-none focus-visible:ring-[3px] md:text-sm",
            className,
          )}
        >
          <span className={cn(!value && "text-muted-foreground italic")}>
            {value ? formatDay(value) : "Not set"}
          </span>
          <CalendarDays className="text-muted-foreground size-4 shrink-0" />
        </button>
        <input
          ref={picker}
          type="date"
          tabIndex={coarse ? undefined : -1}
          aria-hidden={coarse ? undefined : true}
          aria-label={coarse ? name : undefined}
          value={value ?? ""}
          onChange={(event) => onChange(event.target.value || null)}
          // `appearance-none` and a full-size box keep iOS from shrinking the
          // field to its own intrinsic width, which would leave most of the
          // button untouchable.
          className="pointer-events-none absolute inset-0 size-full appearance-none opacity-0 pointer-coarse:pointer-events-auto"
        />
      </div>
      {value && (
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label={`Clear the ${label.toLowerCase()}`}
          className="text-muted-foreground shrink-0 pointer-coarse:size-11"
          onClick={() => onChange(null)}
        >
          <X />
        </Button>
      )}
    </div>
  )
}
