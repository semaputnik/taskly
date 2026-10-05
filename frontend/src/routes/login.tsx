import {
  createFileRoute,
  Link as RouterLink,
  redirect,
} from "@tanstack/react-router"
import { KeyRound } from "lucide-react"
import { type FormEvent, useEffect } from "react"

import { AuthLayout } from "@/components/Common/AuthLayout"
import { PasskeysUnsupported } from "@/components/Common/PasskeysUnsupported"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import useAuth, { isLoggedIn } from "@/hooks/useAuth"
import {
  autofillSupported,
  cancelCeremony,
  passkeysSupported,
} from "@/lib/passkeys"

export const Route = createFileRoute("/login")({
  component: Login,
  beforeLoad: async () => {
    if (isLoggedIn()) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Sign in - Taskly",
      },
    ],
  }),
})

function Login() {
  const supported = passkeysSupported()

  return (
    <AuthLayout>
      <div className="flex flex-col gap-6">
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="text-2xl font-bold">Sign in to Taskly</h1>
          <p className="text-muted-foreground text-sm">
            With the passkey on this device or in your password manager.
          </p>
        </div>
        {supported ? <PasskeySignIn /> : <PasskeysUnsupported />}
      </div>
    </AuthLayout>
  )
}

function PasskeySignIn() {
  const { signInMutation } = useAuth()
  const { mutate } = signInMutation

  // Offer the browser's passkeys in the email field's suggestions as well,
  // waiting in the background until one is picked (FR-12.3).
  useEffect(() => {
    let cancelled = false
    autofillSupported().then((available) => {
      if (available && !cancelled) mutate({ autofill: true })
    })
    return () => {
      cancelled = true
      cancelCeremony()
    }
  }, [mutate])

  const signIn = (event?: FormEvent) => {
    event?.preventDefault()
    // The waiting autofill ceremony gives way to the one asked for.
    cancelCeremony()
    signInMutation.mutate({})
  }

  return (
    <form onSubmit={signIn} className="flex flex-col gap-6">
      <div className="grid gap-4">
        <div className="grid gap-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            name="email"
            data-testid="email-input"
            placeholder="user@example.com"
            type="email"
            // "webauthn" puts the passkeys among the field's suggestions.
            autoComplete="username webauthn"
          />
        </div>
        <LoadingButton
          type="submit"
          loading={
            signInMutation.isPending && !signInMutation.variables?.autofill
          }
        >
          <KeyRound />
          Sign in with passkey
        </LoadingButton>
      </div>

      <div className="flex flex-col gap-2 text-center text-sm">
        <p>
          New to Taskly?{" "}
          <RouterLink to="/signup" className="underline underline-offset-4">
            Create account
          </RouterLink>
        </p>
        <p>
          <RouterLink to="/recover" className="underline underline-offset-4">
            Have a recovery code?
          </RouterLink>
        </p>
      </div>
    </form>
  )
}
