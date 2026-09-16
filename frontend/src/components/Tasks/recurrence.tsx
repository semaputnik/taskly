import type { DueDateScope, Recurrence, RecurrenceFrequency } from "@/client"
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

export const NO_RECURRENCE = "none"

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
