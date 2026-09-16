import { AxiosError } from "axios"

/**
 * Whether the API refused the request as asked (a 4xx), as opposed to failing
 * to answer it. A timeout and a rate limit are the exceptions: they may pass,
 * so they are failures to answer rather than refusals.
 */
export function isRefusal(error: unknown): boolean {
  const status = error instanceof AxiosError ? error.response?.status : 0
  return (
    status !== undefined &&
    status >= 400 &&
    status < 500 &&
    ![408, 429].includes(status)
  )
}
