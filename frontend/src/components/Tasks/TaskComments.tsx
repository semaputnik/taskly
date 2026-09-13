import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { MessageSquare, Pencil, Trash2 } from "lucide-react"
import { useState } from "react"

import { CommentsService, type TaskPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { LoadingButton } from "@/components/ui/loading-button"
import { Textarea } from "@/components/ui/textarea"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface TaskCommentsProps {
  task: TaskPublic
  onSuccess: () => void
}

/**
 * A task's comment thread: a running note read oldest-first, so a human's
 * replies and an AI agent's status reports read back as one narrative
 * (FR-03.1).
 */
const TaskComments = ({ task, onSuccess }: TaskCommentsProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const [draft, setDraft] = useState("")
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editDraft, setEditDraft] = useState("")
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const queryKey = ["comments", task.id]

  const { data: comments, isLoading } = useQuery({
    queryKey,
    queryFn: async () =>
      (await CommentsService.readComments({ path: { task_id: task.id } })).data,
    enabled: isOpen,
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey })

  const addMutation = useMutation({
    mutationFn: (body: string) =>
      CommentsService.createComment({
        path: { task_id: task.id },
        body: { body },
      }),
    onSuccess: () => setDraft(""),
    onError: handleError.bind(showErrorToast),
    onSettled: invalidate,
  })

  const editMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: string }) =>
      CommentsService.updateComment({
        path: { comment_id: id },
        body: { body },
      }),
    onSuccess: () => setEditingId(null),
    onError: handleError.bind(showErrorToast),
    onSettled: invalidate,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      CommentsService.deleteComment({ path: { comment_id: id } }),
    onError: handleError.bind(showErrorToast),
    onSettled: invalidate,
  })

  const startEditing = (id: string, body: string) => {
    setEditingId(id)
    setEditDraft(body)
  }

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        setIsOpen(open)
        if (!open) onSuccess()
      }}
    >
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <MessageSquare />
        Comments
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Comments</DialogTitle>
        </DialogHeader>

        <div className="flex max-h-80 flex-col gap-3 overflow-y-auto">
          {isLoading ? (
            <p className="text-muted-foreground text-sm italic">Loading…</p>
          ) : comments?.data.length ? (
            comments.data.map((comment) => (
              <div key={comment.id} className="rounded-md border p-3 text-sm">
                {editingId === comment.id ? (
                  <div className="flex flex-col gap-2">
                    <Textarea
                      value={editDraft}
                      onChange={(e) => setEditDraft(e.target.value)}
                      autoFocus
                    />
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setEditingId(null)}
                      >
                        Cancel
                      </Button>
                      <LoadingButton
                        size="sm"
                        loading={editMutation.isPending}
                        disabled={!editDraft.trim()}
                        onClick={() =>
                          editMutation.mutate({
                            id: comment.id,
                            body: editDraft.trim(),
                          })
                        }
                      >
                        Save
                      </LoadingButton>
                    </div>
                  </div>
                ) : (
                  <>
                    <p className="whitespace-pre-wrap">{comment.body}</p>
                    <div className="mt-2 flex items-center justify-between">
                      <span className="text-muted-foreground text-xs">
                        {comment.created_at &&
                          new Date(comment.created_at).toLocaleString()}
                      </span>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label="Edit comment"
                          onClick={() => startEditing(comment.id, comment.body)}
                        >
                          <Pencil className="size-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label="Delete comment"
                          onClick={() => deleteMutation.mutate(comment.id)}
                        >
                          <Trash2 className="size-3.5" />
                        </Button>
                      </div>
                    </div>
                  </>
                )}
              </div>
            ))
          ) : (
            <p className="text-muted-foreground text-sm italic">
              No comments yet.
            </p>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <Textarea
            placeholder="Add a comment"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <div className="flex justify-end">
            <LoadingButton
              loading={addMutation.isPending}
              disabled={!draft.trim()}
              onClick={() => addMutation.mutate(draft.trim())}
            >
              Comment
            </LoadingButton>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default TaskComments
