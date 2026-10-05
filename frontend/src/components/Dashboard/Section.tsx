import { QueryErrorResetBoundary } from "@tanstack/react-query"
import { ErrorBoundary } from "react-error-boundary"

import { cn } from "@/lib/utils"
import { textLink } from "./shared"

/**
 * One section of the day page, failing on its own: a request that does not
 * answer costs its section a sentence, not the whole page its bands. Trying
 * again resets the failed queries so they are asked afresh.
 */
export function Section({
  name,
  children,
}: {
  name: string
  children: React.ReactNode
}) {
  return (
    <QueryErrorResetBoundary>
      {({ reset }) => (
        <ErrorBoundary
          onReset={reset}
          fallbackRender={({ resetErrorBoundary }) => (
            <p role="alert" className="text-ink-2 mb-9">
              {name} could not be loaded.{" "}
              <button
                type="button"
                onClick={resetErrorBoundary}
                className={cn(textLink, "text-ink underline")}
              >
                Try again
              </button>
            </p>
          )}
        >
          {children}
        </ErrorBoundary>
      )}
    </QueryErrorResetBoundary>
  )
}
