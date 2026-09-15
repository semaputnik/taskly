import { Check, Copy, TriangleAlert } from "lucide-react"

import { Alert, AlertDescription } from "@/components/ui/alert"
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
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"

interface TokenDialogProps {
  botName: string
  token: string | null
  onClose: () => void
}

/**
 * The one time a bot user's token is on screen. Only its digest is stored, so
 * once this closes nothing can show it again (FR-08.13).
 */
const TokenDialog = ({ botName, token, onClose }: TokenDialogProps) => {
  const [copiedText, copy] = useCopyToClipboard()
  const copied = token !== null && copiedText === token

  return (
    <Dialog
      open={token !== null}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Token for {botName}</DialogTitle>
          <DialogDescription>
            The bot user sends this token as a bearer token to the REST API.
          </DialogDescription>
        </DialogHeader>

        <Alert variant="destructive">
          <TriangleAlert />
          <AlertDescription>
            Copy the token now. It won't be shown again, and it cannot be
            retrieved later.
          </AlertDescription>
        </Alert>

        <div className="flex items-center gap-2">
          <Input
            readOnly
            aria-label="Bot token"
            value={token ?? ""}
            className="font-mono text-xs"
            onFocus={(event) => event.target.select()}
          />
          <Button
            type="button"
            variant="outline"
            onClick={() => token && copy(token)}
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
    </Dialog>
  )
}

export default TokenDialog
