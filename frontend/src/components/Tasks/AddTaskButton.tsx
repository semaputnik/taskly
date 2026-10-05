import { Plus } from "lucide-react"

import { useRecordPanels } from "@/components/Records/panels"
import { Button } from "@/components/ui/button"

/**
 * Capture under the thumb on a phone.
 *
 * Below `md` the navigation folds into a menu sheet, and the page's capture
 * line sits at the top of a screen that scrolls: writing a task down from
 * anywhere would take a trip to the top. This keeps it one tap from every
 * screen, in the corner a thumb rests in. It goes when the capture line is
 * pinned to the bottom of the phone (FR-06.15). It is the primary action, so it is ink; it floats over the page,
 * so like a popover it lifts by a shadow, here a deeper one. An open record's column
 * takes the whole phone screen and covers it: capture is already on screen,
 * or a record is being read.
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
