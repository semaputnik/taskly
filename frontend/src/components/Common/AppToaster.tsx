import { Toaster } from "@/components/ui/sonner"

/**
 * The notices of the whole app, wherever they are raised from — a record's
 * column included, which is no modal and so leaves them within reach. Where
 * they sit and how they look is the Toaster's.
 */
export function AppToaster() {
  return <Toaster closeButton />
}
