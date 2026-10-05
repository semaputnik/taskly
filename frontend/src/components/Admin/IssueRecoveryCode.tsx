import { useMutation } from "@tanstack/react-query"
import { Check, Copy, LifeBuoy } from "lucide-react"
import { useState } from "react"

import type { RecoveryCodeIssued, UserPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"
import { formatDateTime } from "@/lib/dates"
import { issueRecoveryCode, reportUnlessDismissed } from "@/lib/passkeys"

/**
 * Issue a recovery code for a user who has lost every passkey (FR-12.16).
 * It takes a fresh confirmation with the superuser's own passkey, and the
 * code is shown here once: only its digest is kept.
 */
export function IssueRecoveryCode({ user }: { user: UserPublic }) {
  const [issued, setIssued] = useState<RecoveryCodeIssued | null>(null)
  const issue = useMutation({
    mutationFn: () => issueRecoveryCode(user.id),
    onSuccess: setIssued,
    onError: reportUnlessDismissed,
  })

  return (
    <>
      <LoadingButton
        variant="ghost"
        size="sm"
        loading={issue.isPending}
        onClick={() => issue.mutate()}
      >
        <LifeBuoy />
        Issue recovery code
      </LoadingButton>
      <Dialog open={issued !== null}>
        {issued && (
          <RecoveryCodeShown
            email={user.email}
            issued={issued}
            onClose={() => setIssued(null)}
          />
        )}
      </Dialog>
    </>
  )
}

function RecoveryCodeShown({
  email,
  issued,
  onClose,
}: {
  email: string
  issued: RecoveryCodeIssued
  onClose: () => void
}) {
  const [copiedText, copy] = useCopyToClipboard()
  const copied = copiedText === issued.code
  // Shown once and gone on closing, so it closes only on "Done": not on
  // Escape, a click outside, or a corner control (DESIGN.md, Dialogs).
  const refuseDismissal = (event: Event) => event.preventDefault()

  return (
    <DialogContent
      className="sm:max-w-md"
      showCloseButton={false}
      onEscapeKeyDown={refuseDismissal}
      onInteractOutside={refuseDismissal}
    >
      <DialogHeader>
        <DialogTitle>Recovery code for {email}</DialogTitle>
        <DialogDescription>
          Give it to them yourself. They enter it with their email under “Have a
          recovery code?” and make a new passkey. It works once, until{" "}
          {formatDateTime(issued.expires_at)}, and replaces any code issued
          before. It won't be shown again.
        </DialogDescription>
      </DialogHeader>
      <div className="flex items-center gap-2">
        <Input
          readOnly
          aria-label="Recovery code"
          value={issued.code}
          className="font-mono"
          onFocus={(event) => event.target.select()}
        />
        <Button
          type="button"
          variant="outline"
          onClick={() => copy(issued.code)}
        >
          {copied ? <Check /> : <Copy />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <DialogFooter>
        <Button type="button" onClick={onClose}>
          Done
        </Button>
      </DialogFooter>
    </DialogContent>
  )
}
