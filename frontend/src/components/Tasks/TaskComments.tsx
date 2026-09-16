import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Bot, Pencil, Trash2 } from "lucide-react"
import { useState } from "react"

import { CommentsService, type TaskPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { LoadingButton } from "@/components/ui/loading-button"
import { Textarea } from "@/components/ui/textarea"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { useCommentDeletion } from "./commentDeletion"
import { useCommentDraft } from "./commentDraft"

interface TaskCommentsProps {
  task: TaskPublic
}

/**
 * A task's comment thread: a running note read oldest-first, so a human's
 * replies and an AI agent's status reports read back as one narrative
 * (FR-03.1). A comment a bot user wrote names it.
 */
export const TaskComments = ({ task }: TaskCommentsProps) => {
  const draft = useCommentDraft(task.id)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editDraft, setEditDraft] = useState("")
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const queryKey = ["comments", task.id]

  const { data: comments, isLoading } = useQuery({
    queryKey,
    queryFn: async () =>
      (await CommentsService.readComments({ path: { task_id: task.id } })).data,
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey })

  const addMutation = useMutation({
    mutationFn: (body: string) =>
      CommentsService.createComment({
        path: { task_id: task.id },
        body: { body },
      }),
    onSuccess: () => draft.clear(),
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

  const deletion = useCommentDeletion(task.id)
  const shown = comments?.data.filter((comment) => !deletion.isHidden(comment))

  const startEditing = (id: string, body: string) => {
    setEditingId(id)
    setEditDraft(body)
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3">
        {isLoading ? (
          <p className="text-muted-foreground text-sm italic">Loading…</p>
        ) : shown?.length ? (
          shown.map((comment) => (
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
                  {comment.author_bot_user && (
                    <p className="mb-1 flex items-center gap-1.5 font-medium">
                      <Bot
                        className="size-3.5 text-muted-foreground"
                        aria-hidden
                      />
                      {comment.author_bot_user.name}
                      <Badge variant="outline" className="text-xs">
                        {comment.author_bot_user.deleted
                          ? "Deleted bot"
                          : "Bot"}
                      </Badge>
                    </p>
                  )}
                  <p className="whitespace-pre-wrap">{comment.body}</p>
                  <div className="mt-2 flex items-center justify-between">
                    <span className="text-muted-foreground text-xs">
                      {comment.created_at &&
                        new Date(comment.created_at).toLocaleString()}
                    </span>
                    {/* A bot user's comments are append-only, for everyone
                          (FR-03.2, FR-08.10). */}
                    {!comment.author_bot_user && (
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label="Edit comment"
                          className="pointer-coarse:size-11"
                          onClick={() => startEditing(comment.id, comment.body)}
                        >
                          <Pencil className="size-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label="Delete comment"
                          className="pointer-coarse:size-11"
                          onClick={() => deletion.remove(comment)}
                        >
                          <Trash2 className="size-3.5" />
                        </Button>
                      </div>
                    )}
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
        <Textarea placeholder="Add a comment" {...draft.field} />
        <div className="flex justify-end">
          <LoadingButton
            loading={addMutation.isPending}
            disabled={!draft.text.trim()}
            onClick={() => addMutation.mutate(draft.text.trim())}
          >
            Comment
          </LoadingButton>
        </div>
      </div>
    </div>
  )
}

export default TaskComments
