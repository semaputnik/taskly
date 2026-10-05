import { toast } from "sonner"

import { refusalMessage } from "./apiErrors"

/**
 * Notices for the outcome of an act. The message is the notice: severity is
 * carried by the icon beside it, never by a generic heading such as
 * "Success!" above the words that actually say what happened.
 */

export function toastSuccess(
  message: string,
  /** A way onward from what was done, such as opening what was made. */
  action?: { label: string; onClick: () => void },
) {
  toast.success(message, action ? { action } : undefined)
}

/**
 * A task was made from a line, with nothing to confirm it but this notice:
 * it names the task and offers both ways on, to open it and to take it back.
 *
 * Sonner draws the cancel button before the action button, so Open takes the
 * cancel slot and Undo the action slot to read, and be reached, in that order.
 * Both are plain text buttons and either one closes the notice. It stays
 * longer than a receipt: the thumb or the Tab key has to find Undo first.
 */
export function toastCreated(
  message: string,
  { open, undo }: { open: () => void; undo: () => void },
) {
  toast.success(message, {
    duration: 8_000,
    cancel: { label: "Open", onClick: open },
    action: { label: "Undo", onClick: undo },
  })
}

/** Something the reader tried did not work, said without an API behind it. */
export function toastProblem(message: string) {
  toast.error(message)
}

/**
 * A request failed: say what, in the API's words. `lead` goes first when the
 * reader also needs to know what happened as a result.
 */
export function toastError(error: unknown, lead?: string) {
  const message = refusalMessage(error)
  toast.error(lead ? `${lead} ${message}` : message)
}
