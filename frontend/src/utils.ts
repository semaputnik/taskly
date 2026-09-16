import { AxiosError } from "axios"

function extractErrorMessage(err: Error): string {
  if (err instanceof AxiosError) {
    const errDetail = (err.response?.data as any)?.detail
    if (Array.isArray(errDetail) && errDetail.length > 0) {
      return errDetail[0].msg
    }
    if (typeof errDetail === "string") {
      return errDetail
    }
    if (typeof errDetail?.message === "string") {
      return errDetail.message
    }
    return err.message
  }
  // Not an answer from the API: say what the browser knows.
  return err.message || "The request did not reach the server."
}

export const handleError = function (this: (msg: string) => void, err: Error) {
  const errorMessage = extractErrorMessage(err)
  this(errorMessage)
}

// Refusals the client is expected to act on carry a code in the error detail,
// so they can be told apart from any other client error.
function hasErrorCode(err: Error, code: string): boolean {
  if (!(err instanceof AxiosError)) {
    return false
  }
  const detail = (err.response?.data as any)?.detail
  return detail?.code === code
}

/** Completing this task needs a decision about its open subtasks. */
export function isUncompletedSubtasksError(err: Error): boolean {
  return hasErrorCode(err, "task_has_uncompleted_subtasks")
}

/** The name asked for is already one of the user's tags. */
export function isTagExistsError(err: Error): boolean {
  return hasErrorCode(err, "tag_exists")
}

/** Deleting this task would take its subtasks with it. */
export function isSubtaskCascadeError(err: Error): boolean {
  return hasErrorCode(err, "task_has_subtasks")
}

export const getInitials = (name: string): string => {
  return name
    .split(" ")
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase()
}
