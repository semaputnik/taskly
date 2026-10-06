import { useMutation } from "@tanstack/react-query"
import { useState } from "react"

import { BotsService, type BotUserPublic } from "@/client"
import { DayField } from "@/components/Common/DayField"
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
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import { useReportChange } from "@/lib/serverState"
import { toastError } from "@/lib/toasts"
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
  const reportChange = useReportChange()

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
      reportChange({ type: "bot token changed", botId: bot.id })
    },
    onError: (error) => {
      toastError(error)
      reportChange({ type: "bot token changed", botId: bot.id })
    },
  })

  const label = bot.token_revoked_at ? "Issue new token" : "Issue token"

  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        className="text-ink-2 hover:text-ink -mx-2 text-[13.5px] font-medium pointer-coarse:h-11"
        onClick={() => setIsOpen(true)}
      >
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
            <DayField
              id={`expires-${bot.id}`}
              label="Expires on"
              min={today()}
              value={expiresOn || null}
              onChange={(day) => setExpiresOn(day ?? "")}
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
