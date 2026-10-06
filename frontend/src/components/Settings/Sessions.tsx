import { useMutation } from "@tanstack/react-query"

import { UsersService } from "@/client"
import { PropertyRow } from "@/components/Records/RecordPanel"
import useAuth from "@/hooks/useAuth"
import { toastError, toastSuccess } from "@/lib/toasts"
import { act, SettingsSection } from "./Section"

/**
 * Ending every session of the account at once, this one too (FR-12.13). No
 * passkey confirmation is asked for.
 */
export function Sessions() {
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
    <SettingsSection id="sessions" title="Sessions">
      <PropertyRow label="Signed in">
        <div className="flex min-w-0 flex-wrap items-center gap-x-3.5">
          <span className="text-ink-2 text-sm">
            every device you have signed in on
          </span>
          <button
            type="button"
            className={act}
            disabled={signOut.isPending}
            onClick={() => signOut.mutate()}
          >
            {signOut.isPending ? "Signing out…" : "Sign out everywhere"}
          </button>
        </div>
      </PropertyRow>
    </SettingsSection>
  )
}
