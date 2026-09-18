import { Plus } from "lucide-react"

import { useRecordPanels } from "@/components/Records/panels"
import { Button } from "@/components/ui/button"

/**
 * Capture under the thumb on a phone.
 *
 * Below `md` the sidebar, and the Add Task action in it, is an off-canvas
 * sheet: writing a task down took two taps, the first in the far top corner.
 * This keeps it one tap from every screen, in the corner a thumb rests in.
 * It is the primary action, so it takes the teal; it floats over the page, so
 * it takes a real shadow (The Left-the-Page Rule); and it is a rounded square,
 * not a circle, because it is a control and not data (The Pill-Means-Data
 * Rule). An open panel's scrim covers it: capture is already on screen, or a
 * record is being read.
 */
export function AddTaskButton() {
  const { capture } = useRecordPanels()
  return (
    <Button
      aria-label="Add Task"
      onClick={() => capture("task")}
      className="fixed right-4 bottom-[calc(1rem+env(safe-area-inset-bottom))] z-40 size-14 rounded-xl shadow-lg md:hidden [&_svg:not([class*='size-'])]:size-6"
    >
      <Plus aria-hidden />
    </Button>
  )
}
