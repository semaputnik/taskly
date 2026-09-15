import {
  type Control,
  type FieldValues,
  type Path,
  useWatch,
} from "react-hook-form"
import { z } from "zod"

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
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

export const NO_RECURRENCE = "none"

const FREQUENCY_LABELS: Record<RecurrenceFrequency, string> = {
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
  every_n_days: "Every N days",
}

/** The form fields a task form adds to say how the task recurs. */
export const recurrenceShape = {
  recurrence: z.string(),
  interval_days: z.string(),
}

interface RecurrenceValues {
  due_date?: string
  recurrence: string
  interval_days: string
}

/**
 * The checks the API would otherwise turn the form away for: a recurring task
 * needs a due date to count from, and "every N days" needs its N.
 */
export function checkRecurrence(
  values: RecurrenceValues,
  ctx: z.RefinementCtx,
) {
  if (values.recurrence === NO_RECURRENCE) {
    return
  }
  if (!values.due_date) {
    ctx.addIssue({
      code: "custom",
      path: ["due_date"],
      message: "A recurring task needs a due date",
    })
  }
  if (values.recurrence === "every_n_days") {
    const days = Number(values.interval_days)
    if (!Number.isInteger(days) || days < 1) {
      ctx.addIssue({
        code: "custom",
        path: ["interval_days"],
        message: "Enter a whole number of days",
      })
    }
  }
}

export function recurrenceFormValues(recurrence?: Recurrence | null) {
  return {
    recurrence: recurrence?.frequency ?? NO_RECURRENCE,
    interval_days: recurrence?.interval_days?.toString() ?? "",
  }
}

export function toRecurrence(values: RecurrenceValues): Recurrence | null {
  if (values.recurrence === NO_RECURRENCE) {
    return null
  }
  const frequency = values.recurrence as RecurrenceFrequency
  return {
    frequency,
    interval_days:
      frequency === "every_n_days" ? Number(values.interval_days) : null,
  }
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

interface RecurrenceFieldsProps<T extends FieldValues> {
  control: Control<T>
  disabled?: boolean
}

/** "Repeat" plus, for every N days, the N. */
export function RecurrenceFields<T extends FieldValues>({
  control,
  disabled,
}: RecurrenceFieldsProps<T>) {
  const frequency = useWatch({ control, name: "recurrence" as Path<T> })

  return (
    <>
      <FormField
        control={control}
        name={"recurrence" as Path<T>}
        render={({ field }) => (
          <FormItem>
            <FormLabel>Repeat</FormLabel>
            <Select
              onValueChange={field.onChange}
              value={field.value}
              disabled={disabled}
            >
              <FormControl>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
              </FormControl>
              <SelectContent>
                <SelectItem value={NO_RECURRENCE}>Does not repeat</SelectItem>
                {Object.entries(FREQUENCY_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {disabled && (
              <p className="text-sm text-muted-foreground">
                A completed task cannot change how it repeats.
              </p>
            )}
            <FormMessage />
          </FormItem>
        )}
      />

      {frequency === "every_n_days" && (
        <FormField
          control={control}
          name={"interval_days" as Path<T>}
          render={({ field }) => (
            <FormItem>
              <FormLabel>
                Number of days <span className="text-destructive">*</span>
              </FormLabel>
              <FormControl>
                <Input type="number" min={1} step={1} {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
      )}
    </>
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
