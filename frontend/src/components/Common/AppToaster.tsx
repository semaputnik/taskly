import { Toaster } from "@/components/ui/sonner"

/**
 * The notices of the whole app, outside any panel. Where they sit and how
 * they look is the Toaster's: a panel's own toaster shares it, so there is
 * one place for notices wherever they are raised from.
 */
export function AppToaster() {
  return <Toaster closeButton />
}
