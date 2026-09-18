import { Toaster } from "@/components/ui/sonner"
import { useIsMobile } from "@/hooks/useMobile"

/**
 * Where the Add Task button floats (below `md`), notices sit above it rather
 * than on it: its height and bottom gap, plus the safe area it keeps clear of,
 * plus a gap of their own. Sonner switches offsets at 600px, not at `md`, so
 * the same clearance is given to both of its offsets for the whole range.
 */
const CLEAR_OF_ADD_TASK = {
  bottom: "calc(5.5rem + env(safe-area-inset-bottom))",
}

export function AppToaster() {
  const isMobile = useIsMobile()
  return (
    <Toaster
      richColors
      closeButton
      offset={isMobile ? CLEAR_OF_ADD_TASK : undefined}
      mobileOffset={CLEAR_OF_ADD_TASK}
    />
  )
}
