import { useMutation } from "@tanstack/react-query"

import { PaperlessService } from "@/client"
import { toastError } from "@/lib/toasts"

/** "1 PDF", "12 PDFs". */
export const pdfs = (count: number) =>
  `${count} ${count === 1 ? "PDF" : "PDFs"}`

/** The way a test ended, in words. */
export type TestOutcome = { ok: boolean; message: string }

/**
 * Try a connection. With no values it tries the saved one; the connection
 * form passes what is typed and not yet saved. A refused address is a failed
 * test, in the server's words, not an error (FR-04.4).
 */
export function useTestConnection(
  onOutcome: (outcome: TestOutcome | null) => void,
) {
  return useMutation({
    mutationFn: (values?: { url?: string; token?: string }) =>
      PaperlessService.testConnection({ body: values }),
    onMutate: () => onOutcome(null),
    onError: (error) => toastError(error),
    onSuccess: ({ data }) =>
      onOutcome({
        ok: data.ok,
        message: data.ok
          ? "Paperless answered and accepted the token."
          : (data.error ?? "Paperless could not be reached."),
      }),
  })
}

/** What a test came to, said where the reader's eyes already are. */
export function TestResult({ outcome }: { outcome: TestOutcome | null }) {
  // Polite, because the result arrives under the button that asked for it.
  return (
    <p aria-live="polite" className="text-[12.5px] leading-snug text-pretty">
      {outcome && (
        <span className={outcome.ok ? "text-done" : "text-late"}>
          {outcome.message}
        </span>
      )}
    </p>
  )
}
