import { useMutation } from "@tanstack/react-query"
import { type FormEvent, useId, useState } from "react"

import { type PaperlessConnectionPublic, PaperlessService } from "@/client"
import { PropertyRow } from "@/components/Records/RecordPanel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { isRefusal, refusalCode, refusalMessage } from "@/lib/apiErrors"
import { useReportChange } from "@/lib/serverState"
import { toastError, toastSuccess } from "@/lib/toasts"
import {
  type TestOutcome,
  TestResult,
  useTestConnection,
} from "./paperlessTest"

const ADDRESS_MISSING =
  "Enter the address of your Paperless, starting with http:// or https://."
const TOKEN_MISSING = "Enter the API token for this address."
const TOKEN_REQUIRED = "paperless_token_required"

/** Forget a bare trailing slash and stray spaces, as the server does. */
const clean = (url: string) => url.trim().replace(/\/+$/, "")

/** A field's problem, said under it in the server's own words. */
function Problem({ id, children }: { id: string; children: string | null }) {
  if (!children) return null
  return (
    <p
      id={id}
      role="alert"
      className="text-late text-[12.5px] leading-snug text-pretty"
    >
      {children}
    </p>
  )
}

/**
 * Save the connection, and send a refusal to the field it is about: the
 * server holds the rules for an address (FR-04.4, FR-11.3) and for the token
 * that must go with a new one, so each is shown where it was typed, in the
 * server's words. A failure to reach the server is not about a field and is a
 * notice.
 */
function useSaveConnection({
  saved,
  onSaved,
  onAddressProblem,
  onTokenProblem,
}: {
  saved: boolean
  onSaved: () => void
  onAddressProblem: (message: string) => void
  onTokenProblem: (message: string) => void
}) {
  const reportChange = useReportChange()
  return useMutation({
    mutationFn: (body: { url: string; token?: string }) =>
      PaperlessService.setConnection({ body }),
    onSuccess: () => {
      toastSuccess(saved ? "Paperless connection saved" : "Paperless connected")
      onSaved()
    },
    onError: (error) => {
      if (!isRefusal(error)) return toastError(error)
      if (refusalCode(error) === TOKEN_REQUIRED) {
        onTokenProblem(refusalMessage(error))
      } else {
        onAddressProblem(refusalMessage(error))
      }
    },
    onSettled: () => reportChange({ type: "paperless changed" }),
  })
}

const field = "h-[30px] md:text-sm"

/**
 * The address and the token, in place of the Connection line: to connect, or
 * to point the connection somewhere else. The token may be left empty only
 * while the address stays what it is, so a stored token is never sent to an
 * address typed later; the server holds that rule too. Test tries what is
 * typed without saving it.
 */
export function ConnectionForm({
  connection,
  onDone,
}: {
  connection: PaperlessConnectionPublic
  onDone: () => void
}) {
  const ids = { address: useId(), token: useId() }
  const current = connection.connected ? (connection.url ?? "") : ""
  const [url, setUrl] = useState(current)
  const [token, setToken] = useState("")
  const [addressProblem, setAddressProblem] = useState<string | null>(null)
  const [tokenProblem, setTokenProblem] = useState<string | null>(null)
  const [outcome, setOutcome] = useState<TestOutcome | null>(null)

  const save = useSaveConnection({
    saved: connection.connected,
    onSaved: onDone,
    onAddressProblem: setAddressProblem,
    onTokenProblem: setTokenProblem,
  })
  const test = useTestConnection(setOutcome)

  /** The values to send, or null after saying what is missing. */
  const values = () => {
    const address = clean(url)
    setAddressProblem(address ? null : ADDRESS_MISSING)
    const needsToken = !connection.connected || address !== current
    setTokenProblem(needsToken && !token ? TOKEN_MISSING : null)
    if (!address || (needsToken && !token)) return null
    return { url: address, token: token || undefined }
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const body = values()
    if (!body) return
    if (connection.connected && body.url === current && !body.token) {
      return onDone()
    }
    save.mutate(body)
  }

  const busy = save.isPending || test.isPending

  return (
    <form
      noValidate
      onSubmit={submit}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          // Forgets the edit and nothing more: the page stays where it is.
          event.preventDefault()
          event.stopPropagation()
          onDone()
        }
      }}
      className="flex flex-col gap-0.5"
    >
      <PropertyRow label="Address" htmlFor={ids.address}>
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <Input
            id={ids.address}
            inputMode="url"
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
            autoFocus
            placeholder="https://"
            value={url}
            aria-invalid={addressProblem ? true : undefined}
            aria-describedby={
              addressProblem ? `${ids.address}-problem` : undefined
            }
            className={`${field} font-mono md:text-[12.5px]`}
            onChange={(event) => {
              setUrl(event.target.value)
              setAddressProblem(null)
              setOutcome(null)
            }}
          />
          <Problem id={`${ids.address}-problem`}>{addressProblem}</Problem>
        </div>
      </PropertyRow>
      <PropertyRow label="Token" htmlFor={ids.token}>
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <Input
            id={ids.token}
            type="password"
            autoComplete="new-password"
            spellCheck={false}
            value={token}
            aria-invalid={tokenProblem ? true : undefined}
            aria-describedby={`${ids.token}-hint${tokenProblem ? ` ${ids.token}-problem` : ""}`}
            className={field}
            onChange={(event) => {
              setToken(event.target.value)
              setTokenProblem(null)
              setOutcome(null)
            }}
          />
          <Problem id={`${ids.token}-problem`}>{tokenProblem}</Problem>
          <p
            id={`${ids.token}-hint`}
            className="text-ink-3 text-[12.5px] leading-snug text-pretty"
          >
            {connection.connected
              ? "An API token from your Paperless profile. Leave it empty to keep the one stored, as long as the address stays the same."
              : "An API token from your Paperless profile. It is kept so Taskly can use it, and never shown again."}
          </p>
          <div className="flex h-[30px] items-center gap-3 pointer-coarse:h-11">
            <LoadingButton type="submit" size="sm" loading={save.isPending}>
              {connection.connected ? "Save" : "Connect"}
            </LoadingButton>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={busy}
              onClick={() => {
                const body = values()
                if (body) test.mutate(body)
              }}
            >
              {test.isPending ? "Testing…" : "Test"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={save.isPending}
              onClick={onDone}
            >
              Cancel
            </Button>
          </div>
          <TestResult outcome={outcome} />
        </div>
      </PropertyRow>
    </form>
  )
}

/**
 * Replacing the token, in place of the Token line. The stored one is never
 * shown, so there is nothing to edit: a new one is typed, and the address
 * stays what it is.
 */
export function TokenForm({
  connection,
  onDone,
}: {
  connection: PaperlessConnectionPublic
  onDone: () => void
}) {
  const id = useId()
  const [token, setToken] = useState("")
  const [problem, setProblem] = useState<string | null>(null)

  const save = useSaveConnection({
    saved: true,
    onSaved: onDone,
    // Nothing but the token was sent, so whatever was refused is about it.
    onAddressProblem: setProblem,
    onTokenProblem: setProblem,
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!token) return setProblem(TOKEN_MISSING)
    setProblem(null)
    save.mutate({ url: connection.url ?? "", token })
  }

  return (
    <PropertyRow label="Token" htmlFor={id}>
      <form
        noValidate
        onSubmit={submit}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault()
            event.stopPropagation()
            onDone()
          }
        }}
        className="flex min-w-0 flex-1 flex-wrap items-start gap-x-3 gap-y-1"
      >
        <div className="flex min-w-0 flex-1 basis-56 flex-col gap-1">
          <Input
            id={id}
            type="password"
            autoComplete="new-password"
            spellCheck={false}
            autoFocus
            placeholder="New API token"
            value={token}
            aria-invalid={problem ? true : undefined}
            aria-describedby={problem ? `${id}-problem` : undefined}
            className={field}
            onChange={(event) => {
              setToken(event.target.value)
              setProblem(null)
            }}
          />
          <Problem id={`${id}-problem`}>{problem}</Problem>
        </div>
        <div className="flex h-[30px] items-center gap-3 pointer-coarse:h-11">
          <LoadingButton type="submit" size="sm" loading={save.isPending}>
            Save
          </LoadingButton>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={save.isPending}
            onClick={onDone}
          >
            Cancel
          </Button>
        </div>
      </form>
    </PropertyRow>
  )
}
