import { useMutation, useQuery } from "@tanstack/react-query"
import { useId, useState } from "react"

import { type PasskeyPublic, UsersService } from "@/client"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDateTime } from "@/lib/dates"
import {
  addPasskey,
  removePasskey,
  reportUnlessDismissed,
} from "@/lib/passkeys"
import { passkeysQuery, useReportChange } from "@/lib/serverState"
import { toastError, toastSuccess } from "@/lib/toasts"
import { cn } from "@/lib/utils"
import {
  act,
  actQuiet,
  EditActions,
  focusOnMount,
  lineInput,
  Note,
  SettingsSection,
} from "./Section"

/**
 * The account's passkeys as lines, and the way to add one (FR-12.6–FR-12.9).
 * Adding or removing one asks for a fresh passkey confirmation; renaming is a
 * label and does not.
 */
export function Passkeys({ recovered = false }: { recovered?: boolean }) {
  const reportChange = useReportChange()
  const { data, isPending } = useQuery(passkeysQuery())
  const passkeys = data?.data ?? []

  const add = useMutation({
    mutationFn: addPasskey,
    onSuccess: (passkey) => toastSuccess(`Passkey added: ${passkey.name}`),
    onError: reportUnlessDismissed,
    onSettled: () => reportChange({ type: "passkeys changed" }),
  })

  return (
    <SettingsSection
      id="passkeys"
      title="Passkeys"
      count={isPending ? undefined : passkeys.length}
      action={
        <button
          type="button"
          className={act}
          disabled={add.isPending}
          onClick={() => add.mutate()}
        >
          {add.isPending ? "Adding…" : "Add a passkey"}
        </button>
      }
    >
      {recovered && (
        <p data-testid="recovered-notice" className="text-ink my-3 text-sm">
          <span className="font-semibold">You're back in.</span> Your new
          passkey is the last one in the list. Remove any passkey you don't
          recognise.
        </p>
      )}
      <ul data-testid="passkey-list">
        {isPending && <PendingPasskey />}
        {passkeys.map((passkey) => (
          <PasskeyLine
            key={passkey.id}
            passkey={passkey}
            only={passkeys.length === 1}
          />
        ))}
      </ul>
      <Note>
        You sign in with any of these, and adding or removing one asks you to
        confirm with a passkey you already have. The last one cannot be removed.
        Removing one does not sign out the devices it signed in; sign out
        everywhere for that. Lost every passkey? The superuser can issue you a
        recovery code.
      </Note>
    </SettingsSection>
  )
}

const line =
  "border-rule grid min-h-[38px] grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 border-b py-1.5 text-sm"

function PasskeyLine({
  passkey,
  only,
}: {
  passkey: PasskeyPublic
  only: boolean
}) {
  const reportChange = useReportChange()
  const [renaming, setRenaming] = useState(false)
  const [draft, setDraft] = useState(passkey.name)
  const id = useId()

  const rename = useMutation({
    mutationFn: (name: string) =>
      UsersService.renamePasskey({
        path: { passkey_id: passkey.id },
        body: { name },
      }),
    onSuccess: () => setRenaming(false),
    onError: (error) => toastError(error),
    onSettled: () => reportChange({ type: "passkeys changed" }),
  })

  const remove = useMutation({
    mutationFn: () => removePasskey(passkey.id),
    onSuccess: () =>
      toastSuccess(
        `Passkey removed: ${passkey.name}. Devices it signed in stay signed in.`,
      ),
    onError: reportUnlessDismissed,
    onSettled: () => reportChange({ type: "passkeys changed" }),
  })

  const submit = () => {
    const next = draft.trim()
    if (next === "" || next === passkey.name) return setRenaming(false)
    rename.mutate(next)
  }

  return (
    <li className={line}>
      {renaming ? (
        <form
          className="col-span-2 flex flex-wrap items-center gap-x-3 gap-y-1"
          onSubmit={(event) => {
            event.preventDefault()
            submit()
          }}
        >
          <label htmlFor={id} className="sr-only">
            Name of this passkey
          </label>
          <input
            ref={focusOnMount}
            id={id}
            value={draft}
            maxLength={255}
            className={cn(lineInput, "flex-1 basis-56")}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") setRenaming(false)
            }}
          />
          <EditActions
            save="Save"
            pending={rename.isPending}
            onCancel={() => setRenaming(false)}
          />
        </form>
      ) : (
        <>
          <div className="min-w-0">
            <div className="truncate font-medium">{passkey.name}</div>
            <div className="text-ink-3 text-[12.5px]">
              added {formatDateTime(passkey.created_at)} ·{" "}
              {passkey.last_used_at
                ? `last used ${formatDateTime(passkey.last_used_at)}`
                : "never used"}
            </div>
          </div>
          <div className="flex gap-3.5">
            <button
              type="button"
              className={act}
              onClick={() => {
                setDraft(passkey.name)
                setRenaming(true)
              }}
            >
              Rename
              <span className="sr-only"> {passkey.name}</span>
            </button>
            <button
              type="button"
              className={actQuiet}
              // The last passkey stays (FR-12.8): there would be no way back in.
              disabled={only || remove.isPending}
              title={
                only
                  ? "Your only passkey. Add another before removing this one."
                  : undefined
              }
              onClick={() => remove.mutate()}
              aria-label={`Remove ${passkey.name}`}
            >
              {remove.isPending ? "Removing…" : "Remove"}
            </button>
          </div>
        </>
      )}
    </li>
  )
}

function PendingPasskey() {
  return (
    <li className={line} aria-hidden>
      <div className="flex flex-col gap-2">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-3 w-64 max-w-full" />
      </div>
    </li>
  )
}
