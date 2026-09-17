import { useQueryClient } from "@tanstack/react-query"
import { useCallback, useSyncExternalStore } from "react"
import { toast } from "sonner"

import { type CommentPublic, CommentsService } from "@/client"
import { PANEL_TOASTER_ID, settleWhenPanelCloses } from "@/lib/panelNotices"
import { commentsQuery, reportChange } from "@/lib/serverState"
import { toastError } from "@/lib/toasts"

/** How long a deleted comment can still be brought back. */
export const UNDO_WINDOW_MS = 10_000

// Comments deleted on screen whose deletion has not reached the server yet.
// Held outside any component: the window outlives the panel, so closing it or
// moving to another task neither loses the deletion nor cancels it.
let pending: ReadonlySet<string> = new Set()
const listeners = new Set<() => void>()

function setPending(update: (ids: Set<string>) => void) {
  const next = new Set(pending)
  update(next)
  pending = next
  for (const listener of listeners) listener()
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/**
 * Deleting a comment the way that costs a deliberate reader nothing and still
 * catches a stray click: it leaves the thread at once, and an Undo stays on
 * offer for a while before anything is sent.
 *
 * A comment has no soft delete and no restore, so the way back is not to have
 * gone yet: the server is asked only once the window lapses or the notice is
 * dismissed. Undo therefore returns the very same comment, author and time
 * included. Leaving the page inside the window keeps the comment, which is the
 * safe way for that to fail.
 *
 * Only the reader's own comments reach this: a bot user's are append-only and
 * the thread offers them no delete (FR-03.2, FR-08.10).
 */
export function useCommentDeletion(taskId: string) {
  const queryClient = useQueryClient()
  const hidden = useSyncExternalStore(subscribe, () => pending)

  const remove = useCallback(
    (comment: CommentPublic) => {
      setPending((ids) => ids.add(comment.id))
      let settled = false
      // The panel's closing is a dismissal: the deletion goes ahead.
      const withdraw = settleWhenPanelCloses(() => {
        void send()
        toast.dismiss(notice)
      })

      const undo = () => {
        if (settled) return
        settled = true
        withdraw()
        setPending((ids) => ids.delete(comment.id))
      }

      async function send() {
        if (settled) return
        settled = true
        withdraw()
        try {
          await CommentsService.deleteComment({
            path: { comment_id: comment.id },
          })
          // Out of the cached thread before it is out of the pending set, so
          // it does not flash back while the refetch is on its way.
          queryClient.setQueryData(
            commentsQuery(taskId).queryKey,
            (thread) =>
              thread && {
                ...thread,
                data: thread.data.filter((c) => c.id !== comment.id),
                count: thread.count - 1,
              },
          )
        } catch (error) {
          toastError(error, "The comment could not be deleted, so it is back.")
        } finally {
          setPending((ids) => ids.delete(comment.id))
          reportChange(queryClient, { type: "comments changed", taskId })
        }
      }

      const notice = toast("Comment deleted", {
        toasterId: PANEL_TOASTER_ID,
        description: excerpt(comment.body),
        duration: UNDO_WINDOW_MS,
        action: { label: "Undo", onClick: undo },
        onAutoClose: () => void send(),
        onDismiss: () => void send(),
      })
    },
    [queryClient, taskId],
  )

  return {
    remove,
    /** Whether a comment is on its way out and should not be shown. */
    isHidden: (comment: CommentPublic) => hidden.has(comment.id),
  }
}

function excerpt(body: string): string {
  const line = body.replace(/\s+/g, " ").trim()
  return line.length > 80 ? `${line.slice(0, 79)}…` : line
}
