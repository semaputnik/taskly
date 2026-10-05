import { useMutation, useQuery } from "@tanstack/react-query"
import { KeyRound, ShieldAlert } from "lucide-react"

import { type PasskeyPublic, UsersService } from "@/client"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"
import { formatDateTime } from "@/lib/dates"
import {
  addPasskey,
  removePasskey,
  reportUnlessDismissed,
} from "@/lib/passkeys"
import { passkeysQuery, useReportChange } from "@/lib/serverState"
import { toastError, toastSuccess } from "@/lib/toasts"

/**
 * The account's passkeys, and signing out everywhere (FR-12.6–FR-12.9,
 * FR-12.13). Adding or removing one asks for a fresh passkey confirmation;
 * signing out everywhere does not.
 */
const Passkeys = ({ recovered = false }: { recovered?: boolean }) => (
  <div className="flex max-w-xl flex-col gap-6">
    {recovered && (
      <Alert data-testid="recovered-notice">
        <ShieldAlert />
        <AlertTitle>You're back in</AlertTitle>
        <AlertDescription>
          Your new passkey is the last one in the list. Remove any passkey you
          don't recognise.
        </AlertDescription>
      </Alert>
    )}
    <PasskeyList />
    <SignOutEverywhere />
  </div>
)

function PasskeyList() {
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
    <section className="bg-card rounded-lg border p-6">
      <h2 className="text-lg font-semibold">Passkeys</h2>
      <p className="text-muted-foreground mt-1 text-sm">
        You sign in with any of these. Adding or removing one asks you to
        confirm with a passkey you already have. Removing one does not sign out
        the devices it signed in; sign out everywhere for that.
      </p>
      <ul className="mt-4 divide-y" data-testid="passkey-list">
        {isPending && <PendingPasskey />}
        {passkeys.map((passkey) => (
          <PasskeyRow
            key={passkey.id}
            passkey={passkey}
            only={passkeys.length === 1}
          />
        ))}
      </ul>
      <LoadingButton
        className="mt-4"
        variant="outline"
        loading={add.isPending}
        onClick={() => add.mutate()}
      >
        <KeyRound />
        Add a passkey
      </LoadingButton>
    </section>
  )
}

function PasskeyRow({
  passkey,
  only,
}: {
  passkey: PasskeyPublic
  only: boolean
}) {
  const reportChange = useReportChange()
  const remove = useMutation({
    mutationFn: () => removePasskey(passkey.id),
    onSuccess: () =>
      toastSuccess(
        `Passkey removed: ${passkey.name}. Devices it signed in stay signed in.`,
      ),
    onError: reportUnlessDismissed,
    onSettled: () => reportChange({ type: "passkeys changed" }),
  })

  return (
    <li className="flex items-center justify-between gap-4 py-3">
      <div className="min-w-0">
        <p className="truncate font-medium">{passkey.name}</p>
        <p className="text-muted-foreground text-sm">
          Created {formatDateTime(passkey.created_at)} ·{" "}
          {passkey.last_used_at ? (
            `last used ${formatDateTime(passkey.last_used_at)}`
          ) : (
            <span className="italic">never used</span>
          )}
        </p>
      </div>
      <LoadingButton
        variant="ghost"
        size="sm"
        loading={remove.isPending}
        // The last passkey stays (FR-12.8): there would be no way back in.
        disabled={only}
        title={
          only
            ? "Your only passkey. Add another before removing this one."
            : undefined
        }
        onClick={() => remove.mutate()}
        aria-label={`Remove ${passkey.name}`}
      >
        Remove
      </LoadingButton>
    </li>
  )
}

function PendingPasskey() {
  return (
    <li className="flex items-center justify-between gap-4 py-3">
      <div className="flex flex-col gap-2">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-3 w-64" />
      </div>
      <Skeleton className="h-8 w-16" />
    </li>
  )
}

function SignOutEverywhere() {
  const { logout } = useAuth()
  const signOut = useMutation({
    mutationFn: () => UsersService.signOutEverywhere(),
    onSuccess: () => {
      toastSuccess("Signed out on every device")
      logout()
    },
    onError: (error) => toastError(error),
  })

  return (
    <section className="bg-card rounded-lg border p-6">
      <h2 className="text-lg font-semibold">Sign out everywhere</h2>
      <p className="text-muted-foreground mt-1 text-sm">
        Ends every session of your account, on every device, this one too.
        Removing a passkey does not do this: do it after removing one you don't
        trust.
      </p>
      <LoadingButton
        className="mt-4"
        variant="outline"
        loading={signOut.isPending}
        onClick={() => signOut.mutate()}
      >
        Sign out everywhere
      </LoadingButton>
    </section>
  )
}

export default Passkeys
