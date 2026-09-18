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
