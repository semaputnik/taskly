import { Plus } from "lucide-react"

import { useRecordPanels } from "@/components/Records/panels"
import { Button } from "@/components/ui/button"

/**
 * Capture under the thumb on a phone.
 *
 * Below `md` the navigation, and the Add a task entry in it, folds into a
 * menu sheet: writing a task down would take two taps, the first in the far
 * top corner. This keeps it one tap from every screen, in the corner a thumb
 * rests in. It is the primary action, so it is ink; it floats over the page,
 * so it takes the one real shadow in the app. An open panel's scrim covers
 * it: capture is already on screen, or a record is being read.
 */
export function AddTaskButton() {
  const { capture } = useRecordPanels()
  return (
    <Button
      aria-label="Add a task"
      onClick={() => capture("task")}
      className="fixed right-4 bottom-[calc(1rem+env(safe-area-inset-bottom))] z-40 size-13 rounded-full shadow-[0_6px_16px_rgb(0_0_0/0.18)] md:hidden [&_svg:not([class*='size-'])]:size-[22px]"
    >
      <Plus aria-hidden strokeWidth={2} />
    </Button>
  )
}
