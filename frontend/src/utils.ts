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
    return err.message
  }
  return "Something went wrong."
}

export const handleError = function (this: (msg: string) => void, err: Error) {
  const errorMessage = extractErrorMessage(err)
  this(errorMessage)
}

// The API refuses to complete a task with open subtasks and says so with this
// code, so the refusal can be told apart from any other client error.
const UNCOMPLETED_SUBTASKS_CODE = "task_has_uncompleted_subtasks"

export function isUncompletedSubtasksError(err: Error): boolean {
  if (!(err instanceof AxiosError)) {
    return false
  }
  const detail = (err.response?.data as any)?.detail
  return detail?.code === UNCOMPLETED_SUBTASKS_CODE
}

export const getInitials = (name: string): string => {
  return name
    .split(" ")
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase()
}
