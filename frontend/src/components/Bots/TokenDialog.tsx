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
import { formatDateTime } from "@/lib/dates"

interface TokenDialogProps {
  botName: string
  token: string | null
  expiresAt?: string | null
  onClose: () => void
}

/**
 * What a one-time reveal calls the thing it shows, and says about it. A
 * token and a webhook's secret are shown the same way and for the same
 * reason, so they share the dialog and differ only in these words.
 */
export interface Secret {
  title: string
  description: string
  /** "token" or "secret": what the buttons and the warnings call it. */
  noun: string
  /** The accessible name of the field the value is in. */
  fieldLabel: string
  /** What follows once it is gone, finishing "it cannot be shown again and …". */
  consequence: string
  /** A line under the value: when a token expires. */
  note?: string
  value: string
}

/**
 * The one time a bot user's token is on screen. Only its digest is stored, so
 * once this closes nothing can show it again (FR-08.13).
 */
const TokenDialog = ({
  botName,
  token,
  expiresAt,
  onClose,
}: TokenDialogProps) => (
  <SecretDialog
    onClose={onClose}
    secret={
      token === null
        ? null
        : {
            title: `Token for ${botName}`,
            description:
              "The bot user sends this token as a bearer token to the REST API.",
            noun: "token",
            fieldLabel: "Bot token",
            consequence: "the bot user needs a new one",
            note: expiresAt
              ? `It expires ${formatDateTime(expiresAt)}.`
              : "It works until you revoke it.",
            value: token,
          }
    }
  />
)

/**
 * The reveal of anything shown once and never again.
 *
 * It is the only dialog in the product whose dismissal cannot be taken back,
 * so it is not dismissed like the others: Escape and a click outside leave it
 * open, there is no corner control, and moving on takes an explicit word that
 * the value is stored — plus a second, deliberate step if it was never copied.
 */
export const SecretDialog = ({
  secret,
  onClose,
}: {
  secret: Secret | null
  onClose: () => void
}) => (
  <Dialog open={secret !== null}>
    {secret !== null && (
      // Keyed by the value, so a new one starts with nothing acknowledged.
      <SecretReveal key={secret.value} secret={secret} onClose={onClose} />
    )}
  </Dialog>
)

function SecretReveal({
  secret,
  onClose,
}: {
  secret: Secret
  onClose: () => void
}) {
  const { title, description, noun, fieldLabel, consequence, note, value } =
    secret
  const [copiedText, copy] = useCopyToClipboard()
  // "Copied" on the button fades after a moment; having copied does not.
  const [everCopied, setEverCopied] = useState(false)
  const [stored, setStored] = useState(false)
  const [confirmingUncopied, setConfirmingUncopied] = useState(false)
  const [dismissalRefused, setDismissalRefused] = useState(false)
  const storedId = useId()

  const refuseDismissal = (event: Event) => {
    event.preventDefault()
    setDismissalRefused(true)
  }

  const leave = () => {
    if (!everCopied && !confirmingUncopied) {
      setConfirmingUncopied(true)
      return
    }
    onClose()
  }

  return (
    <DialogContent
      className="sm:max-w-lg"
      showCloseButton={false}
      onEscapeKeyDown={refuseDismissal}
      onInteractOutside={refuseDismissal}
    >
      <DialogHeader>
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription>{description}</DialogDescription>
      </DialogHeader>

      <Alert variant="destructive">
        <TriangleAlert />
        <AlertDescription>
          Copy the {noun} now. It won't be shown again, and it cannot be
          retrieved later.
        </AlertDescription>
      </Alert>

      <div className="flex items-center gap-2">
        <Input
          readOnly
          aria-label={fieldLabel}
          value={value}
          className="font-mono text-base md:text-xs"
          onFocus={(event) => event.target.select()}
          onCopy={() => setEverCopied(true)}
        />
        <Button
          type="button"
          variant="outline"
          onClick={async () => {
            if (await copy(value)) setEverCopied(true)
          }}
        >
          {copiedText === value ? <Check /> : <Copy />}
          {copiedText === value ? "Copied" : "Copy"}
        </Button>
      </div>

      {note && <p className="text-muted-foreground text-sm">{note}</p>}

      <div className="flex items-center gap-2">
        <Checkbox
          id={storedId}
          checked={stored}
          onCheckedChange={(checked) => {
            setStored(checked === true)
            setConfirmingUncopied(false)
          }}
        />
        <Label htmlFor={storedId} className="font-normal">
          I have stored this {noun} somewhere safe
        </Label>
      </div>

      <div aria-live="polite" className="empty:hidden">
        {confirmingUncopied ? (
          <Alert variant="destructive">
            <TriangleAlert />
            <AlertDescription>
              You have not copied the {noun}. Once this closes, it cannot be
              shown again and {consequence}.
            </AlertDescription>
          </Alert>
        ) : dismissalRefused && !stored ? (
          <p className="text-muted-foreground text-sm">
            This stays open until you confirm the {noun} is stored.
          </p>
        ) : null}
      </div>

      <DialogFooter>
        {confirmingUncopied ? (
          <>
            <Button
              type="button"
              variant="outline"
              onClick={() => setConfirmingUncopied(false)}
            >
              Back to the {noun}
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
