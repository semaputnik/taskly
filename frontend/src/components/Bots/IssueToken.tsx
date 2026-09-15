import { useMutation, useQueryClient } from "@tanstack/react-query"
import { KeyRound } from "lucide-react"
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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { useShowIssuedToken } from "./IssuedToken"
import { expiryFromDate, today } from "./tokens"

/**
 * Issues a bot user's token, first or again after a revoke (FR-08.16), with an
 * optional expiry (FR-08.14).
 */
const IssueToken = ({ bot }: { bot: BotUserPublic }) => {
  const [isOpen, setIsOpen] = useState(false)
  const [expiresOn, setExpiresOn] = useState("")
  const showIssuedToken = useShowIssuedToken()
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () =>
      BotsService.issueBotUserToken({
        path: { bot_user_id: bot.id },
        body: { expires_at: expiryFromDate(expiresOn) ?? null },
      }),
    onSuccess: ({ data }) => {
      setIsOpen(false)
      setExpiresOn("")
      showIssuedToken({
        botName: bot.name,
        token: data.token,
        expiresAt: data.expires_at,
      })
    },
    onError: (error) => {
      handleError.call(showErrorToast, error)
      queryClient.invalidateQueries({ queryKey: ["bots"] })
    },
  })

  const label = bot.token_revoked_at ? "Issue new token" : "Issue token"

  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setIsOpen(true)}>
        <KeyRound />
        {label}
      </Button>

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>
              {label} for {bot.name}
            </DialogTitle>
            <DialogDescription>
              The bot user keeps its name and scope. Its token is shown once,
              right after it is issued.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor={`expires-${bot.id}`}>Expires on (optional)</Label>
            <Input
              id={`expires-${bot.id}`}
              type="date"
              min={today()}
              value={expiresOn}
              onChange={(event) => setExpiresOn(event.target.value)}
            />
            <p className="text-muted-foreground text-xs">
              Leave empty for a token that works until you revoke it.
            </p>
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" disabled={mutation.isPending}>
                Cancel
              </Button>
            </DialogClose>
            <LoadingButton
              loading={mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              Issue
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

export default IssueToken
