/**
 * Notices raised from inside an open record panel, and what becomes of them
 * when the panel goes.
 *
 * A panel is a modal sheet: while it is open, nothing outside it can be
 * clicked or reached with Tab. A notice that offers an action — Undo — is
 * therefore shown by a toaster inside the panel, where the reader can use it.
 * That toaster leaves with the panel, so an action still on offer at that
 * point is settled as if its notice had been dismissed.
 */

/** The toaster a record panel carries; pass as `toasterId`. */
export const PANEL_TOASTER_ID = "record-panel"

const settleOnClose = new Set<() => void>()

/** Settle this if the panel closes first. Returns the way to withdraw it. */
export function settleWhenPanelCloses(settle: () => void): () => void {
  settleOnClose.add(settle)
  return () => settleOnClose.delete(settle)
}

/** The panel is going: settle everything its notices still hold open. */
export function settlePanelNotices() {
  for (const settle of [...settleOnClose]) settle()
}
