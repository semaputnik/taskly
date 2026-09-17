import { AxiosError } from "axios"

/**
 * API refusals: what a failed response means, answered the way callers ask.
 *
 * Everything that reads a failed request — the query client, a toast, a
 * control deciding whether to raise a prompt — asks here rather than poking
 * at the response itself.
 */

/** The codes the frontend acts on, as the API sends them. */
export const Refusal = {
  /** Moving a task to done needs a decision about its open subtasks. */
  OPEN_SUBTASKS: "task_has_uncompleted_subtasks",
  /** Deleting a task would take its subtasks with it. */
  HAS_SUBTASKS: "task_has_subtasks",
  /** The name asked for is already one of the user's tags. */
  TAG_EXISTS: "tag_exists",
  /** A batch cannot move a recurring task's due date. */
  TASK_REPEATS: "task_repeats",
  /** A batch could not be done whole; the refusals say which tasks and why. */
  BULK_REFUSED: "bulk_refused",
} as const

/** One task a batch could not change, and why. */
export interface BatchRefusal {
  task_id: string
  code: string
  message: string
}

const statusOf = (error: unknown): number | undefined =>
  error instanceof AxiosError ? error.response?.status : undefined

const detailOf = (error: unknown): unknown =>
  error instanceof AxiosError
    ? (error.response?.data as { detail?: unknown } | undefined)?.detail
    : undefined

/**
 * Whether the session is gone: the API no longer accepts the credential, and
 * signing in again is the only way on. A 403 is not this — it refuses a
 * caller the API knows.
 */
export function isSessionGone(error: unknown): boolean {
  return statusOf(error) === 401
}

/**
 * Whether the API refused the request as asked (a 4xx), as opposed to failing
 * to answer it. A timeout and a rate limit are the exceptions: they may pass,
 * so they are failures to answer rather than refusals.
 */
export function isRefusal(error: unknown): boolean {
  const status = statusOf(error)
  return (
    status !== undefined &&
    status >= 400 &&
    status < 500 &&
    ![408, 429].includes(status)
  )
}

/** The code a refusal carries, if it carries one. */
export function refusalCode(error: unknown): string | undefined {
  const detail = detailOf(error) as { code?: unknown } | undefined
  return typeof detail?.code === "string" ? detail.code : undefined
}

/** What to tell the reader: what failed, in the API's words where it gave some. */
export function refusalMessage(error: unknown): string {
  if (!(error instanceof AxiosError)) {
    // Not an answer from the API: say what the browser knows.
    return (
      (error instanceof Error && error.message) ||
      "The request did not reach the server."
    )
  }
  const detail = detailOf(error) as unknown
  if (Array.isArray(detail) && detail.length > 0) {
    return detail[0].msg
  }
  if (typeof detail === "string") {
    return detail
  }
  const message = (detail as { message?: unknown } | undefined)?.message
  if (typeof message === "string") {
    return message
  }
  return error.message
}

/** The tasks a batch refused, when that is what came back. */
export function batchRefusals(error: unknown): BatchRefusal[] | null {
  if (refusalCode(error) !== Refusal.BULK_REFUSED) return null
  const detail = detailOf(error) as { refusals?: BatchRefusal[] }
  return detail.refusals ?? []
}
