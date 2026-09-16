import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { useState } from "react"

import { BotsService, type BotUserPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface DeleteBotUserProps {
  bot: BotUserPublic
  onSuccess: () => void
}

/**
 * Deletes a bot user, behind a confirmation: its token stops working at once
 * and there is no restoring it (FR-08.18, FR-08.20). What it did and what it
 * was assigned keep its name (FR-08.19, FR-08.21).
 */
const DeleteBotUser = ({ bot, onSuccess }: DeleteBotUserProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () =>
      BotsService.deleteBotUser({ path: { bot_user_id: bot.id } }),
    onSuccess: () => {
      showSuccessToast(`“${bot.name}” was deleted`)
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["bots"] })
      // Its own record still reads — marked deleted now (FR-08.19) — so the
      // panel must not be left holding the copy from before.
      queryClient.invalidateQueries({ queryKey: ["bot", bot.id] })
      // Tasks assigned to it now show it as deleted.
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
    },
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      {/* The one act with no undo gets the one control in the panel's
          corner: no menu to open first, and no neighbours to catch a stray
          click. */}
      <Button
        variant="ghost"
        size="icon"
        aria-label="Delete bot user"
        className="text-muted-foreground hover:text-destructive"
        onClick={() => setIsOpen(true)}
      >
        <Trash2 />
      </Button>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delete {bot.name}?</DialogTitle>
          <DialogDescription>
            Its token stops working right away, and the bot can't be restored.
            Tasks assigned to it stay assigned to it, and the activity log still
            names it.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              Cancel
            </Button>
          </DialogClose>
          <LoadingButton
            variant="destructive"
            loading={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            Delete
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default DeleteBotUser
