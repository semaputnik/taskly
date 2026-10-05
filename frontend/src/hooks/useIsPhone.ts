import { useSyncExternalStore } from "react"

/** Below Tailwind's `md`: the width at which the navigation folds away. */
const PHONE = "(max-width: 767.98px)"

/**
 * Whether the screen is a phone's width, following changes as they happen.
 * It is for what CSS cannot say alone: which control to mount, and which way
 * a list opens. Whatever CSS can do by itself it should.
 */
export function useIsPhone(): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const query = window.matchMedia(PHONE)
      query.addEventListener("change", onChange)
      return () => query.removeEventListener("change", onChange)
    },
    () => window.matchMedia(PHONE).matches,
    () => false,
  )
}
