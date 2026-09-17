import { useMutation } from "@tanstack/react-query"
import { Ban } from "lucide-react"
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
import { useReportChange } from "@/lib/serverState"
import { toastError, toastSuccess } from "@/lib/toasts"

/**
 * Revokes a bot user's token. Unlike most things here it cuts an integration
 * off mid-work, so it is confirmed first (FR-08.15).
 */
const RevokeToken = ({ bot }: { bot: BotUserPublic }) => {
  const [isOpen, setIsOpen] = useState(false)
  const reportChange = useReportChange()

  const mutation = useMutation({
    mutationFn: () =>
      BotsService.revokeBotUserToken({ path: { bot_user_id: bot.id } }),
    onSuccess: () => {
      toastSuccess(`The token for “${bot.name}” was revoked`)
      setIsOpen(false)
    },
    onError: (error) => toastError(error),
    // Without the panel's copy refreshed too, it would still say the token
    // is active.
    onSettled: () => reportChange({ type: "bot token changed", botId: bot.id }),
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <Button variant="outline" size="sm" onClick={() => setIsOpen(true)}>
        <Ban />
        Revoke
      </Button>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Revoke the token for {bot.name}?</DialogTitle>
          <DialogDescription>
            Requests with this token are refused from now on. The bot user keeps
            its name and scope, and you can issue it a new token later.
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
            Revoke
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default RevokeToken
