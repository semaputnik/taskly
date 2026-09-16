import { useEffect, useState } from "react"

import type { DueDateScope, Recurrence, RecurrenceFrequency } from "@/client"
import { RecurrenceSchema } from "@/client/schemas.gen"
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
import { Input } from "@/components/ui/input"
import useCustomToast from "@/hooks/useCustomToast"

export const NO_RECURRENCE = "none"

/**
 * The shortest "every N days" rule, read from the API's own schema rather than
 * restated: the server enforces it for every client, bot users included, and
 * a second copy here would be free to drift (FR-01.13).
 */
export const MIN_INTERVAL_DAYS =
  RecurrenceSchema.properties.interval_days.anyOf[0].minimum

const FREQUENCY_LABELS: Record<RecurrenceFrequency, string> = {
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
  every_n_days: "Every N days",
}

export function sameRecurrence(a?: Recurrence | null, b?: Recurrence | null) {
  return (
    (a?.frequency ?? null) === (b?.frequency ?? null) &&
    (a?.interval_days ?? null) === (b?.interval_days ?? null)
  )
}

export function describeRecurrence(recurrence: Recurrence): string {
  if (recurrence.frequency === "every_n_days") {
    return `Every ${recurrence.interval_days} days`
  }
  return FREQUENCY_LABELS[recurrence.frequency]
}

/**
 * The N of an "every N days" rule, saved when focus leaves it.
 *
 * A value the API would refuse is not sent: the field goes back to the stored
 * interval and says why, so what is on screen is always the rule in force.
 */
export function IntervalDaysField({
  value,
  onCommit,
  className,
}: {
  value: number
  onCommit: (days: number) => void
  className?: string
}) {
  const [draft, setDraft] = useState(String(value))
  const { showErrorToast } = useCustomToast()
  useEffect(() => setDraft(String(value)), [value])

  const commit = () => {
    const days = Number(draft)
    if (!Number.isInteger(days) || days < MIN_INTERVAL_DAYS) {
      setDraft(String(value))
      showErrorToast(
        `Every N days starts at ${MIN_INTERVAL_DAYS} days. For a task that comes back daily, choose Every day.`,
      )
      return
    }
    if (days !== value) onCommit(days)
  }

  return (
    <Input
      type="number"
      min={MIN_INTERVAL_DAYS}
      step={1}
      aria-label="Days between repeats"
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur()
        if (e.key === "Escape") setDraft(String(value))
      }}
      className={className}
    />
  )
}

interface DueDateScopeDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onChoose: (scope: DueDateScope) => void
  pending: boolean
}

/**
 * Moving the due date of a recurring task asks what happens to the rest of
 * the routine. Both outcomes are offered side by side and neither is the
 * default, the same as the API (FR-01.17).
 */
export function DueDateScopeDialog({
  open,
  onOpenChange,
  onChoose,
  pending,
}: DueDateScopeDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>This task repeats</DialogTitle>
          <DialogDescription>
            Choose whether the new due date is a one-off or reschedules the
            routine from here on.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="sm:flex-col sm:gap-2">
          <Button
            variant="outline"
            disabled={pending}
            onClick={() => onChoose("this_occurrence")}
          >
            Only this occurrence
          </Button>
          <Button
            variant="outline"
            disabled={pending}
            onClick={() => onChoose("this_and_following")}
          >
            This and all following occurrences
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
