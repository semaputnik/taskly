import { CalendarDays, X } from "lucide-react"
import { useRef } from "react"

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
 */
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
    <div className="relative flex items-center gap-1">
      <button
        id={id}
        type="button"
        aria-label={
          value ? `${label}: ${formatDay(value)}` : `${label}: not set`
        }
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
        tabIndex={-1}
        aria-hidden
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value || null)}
        className="pointer-events-none absolute inset-0 opacity-0"
      />
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
