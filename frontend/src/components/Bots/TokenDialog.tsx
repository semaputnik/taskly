import { Check, Copy, TriangleAlert } from "lucide-react"
import { useId, useState } from "react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"
import { formatDateTime } from "./tokens"

interface TokenDialogProps {
  botName: string
  token: string | null
  expiresAt?: string | null
  onClose: () => void
}

/**
 * The one time a bot user's token is on screen. Only its digest is stored, so
 * once this closes nothing can show it again (FR-08.13).
 *
 * It is the only dialog in the product whose dismissal cannot be taken back,
 * so it is not dismissed like the others: Escape and a click outside leave it
 * open, there is no corner control, and moving on takes an explicit word that
 * the token is stored — plus a second, deliberate step if it was never copied.
 */
const TokenDialog = (props: TokenDialogProps) => (
  <Dialog open={props.token !== null}>
    {props.token !== null && (
      // Keyed by the token, so a new one starts with nothing acknowledged.
      <TokenReveal key={props.token} {...props} token={props.token} />
    )}
  </Dialog>
)

function TokenReveal({
  botName,
  token,
  expiresAt,
  onClose,
}: TokenDialogProps & { token: string }) {
  const [copiedText, copy] = useCopyToClipboard()
  // "Copied" on the button fades after a moment; having copied does not.
  const [everCopied, setEverCopied] = useState(false)
  const [stored, setStored] = useState(false)
  const [warning, setWarning] = useState(false)
  const [held, setHeld] = useState(false)
  const storedId = useId()

  const hold = (event: Event) => {
    event.preventDefault()
    setHeld(true)
  }

  const leave = () => {
    if (!everCopied && !warning) {
      setWarning(true)
      return
    }
    onClose()
  }

  return (
    <DialogContent
      className="sm:max-w-lg"
      showCloseButton={false}
      onEscapeKeyDown={hold}
      onInteractOutside={hold}
    >
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
          value={token}
          className="font-mono text-xs"
          onFocus={(event) => event.target.select()}
          onCopy={() => setEverCopied(true)}
        />
        <Button
          type="button"
          variant="outline"
          onClick={async () => {
            if (await copy(token)) setEverCopied(true)
          }}
        >
          {copiedText === token ? <Check /> : <Copy />}
          {copiedText === token ? "Copied" : "Copy"}
        </Button>
      </div>

      <p className="text-muted-foreground text-sm">
        {expiresAt
          ? `It expires ${formatDateTime(expiresAt)}.`
          : "It works until you revoke it."}
      </p>

      <div className="flex items-center gap-2">
        <Checkbox
          id={storedId}
          checked={stored}
          onCheckedChange={(checked) => {
            setStored(checked === true)
            setWarning(false)
          }}
        />
        <Label htmlFor={storedId} className="font-normal">
          I have stored this token somewhere safe
        </Label>
      </div>

      <div aria-live="polite" className="empty:hidden">
        {warning ? (
          <Alert variant="destructive">
            <TriangleAlert />
            <AlertDescription>
              You have not copied the token. Once this closes, it cannot be
              shown again and the bot user needs a new one.
            </AlertDescription>
          </Alert>
        ) : held && !stored ? (
          <p className="text-muted-foreground text-sm">
            This stays open until you confirm the token is stored.
          </p>
        ) : null}
      </div>

      <DialogFooter>
        {warning ? (
          <>
            <Button
              type="button"
              variant="outline"
              onClick={() => setWarning(false)}
            >
              Back to the token
            </Button>
            <Button type="button" variant="destructive" onClick={leave}>
              Close without copying
            </Button>
          </>
        ) : (
          <Button type="button" disabled={!stored} onClick={leave}>
            Done
          </Button>
        )}
      </DialogFooter>
    </DialogContent>
  )
}

export default TokenDialog
