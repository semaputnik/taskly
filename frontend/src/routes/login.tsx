import { createFileRoute, redirect } from "@tanstack/react-router"
import { KeyRound } from "lucide-react"
import { type FormEvent, useEffect } from "react"

import {
  AuthLink,
  AuthLinks,
  AuthScreen,
  authAction,
  PasskeysUnsupported,
} from "@/components/Auth/AuthScreen"
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
    <AuthScreen
      heading="Sign in"
      lede="Your browser will offer the passkeys it holds for this installation. Nothing to type."
    >
      {supported ? <PasskeySignIn /> : <PasskeysUnsupported />}
      <AuthLinks>
        <AuthLink lead="Lost every passkey?" to="/recover">
          Use a recovery code
        </AuthLink>
        <AuthLink lead="New here?" to="/signup">
          Create an account
        </AuthLink>
      </AuthLinks>
    </AuthScreen>
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
    <form onSubmit={signIn}>
      {/* The browser's passkey suggestions attach to an email field, and the
          screen asks for nothing typed: the field is the autofill ceremony's
          anchor and is left out of sight and out of the tab order. */}
      <input
        data-testid="email-input"
        name="email"
        type="email"
        // "webauthn" puts the passkeys among the field's suggestions.
        autoComplete="username webauthn"
        tabIndex={-1}
        aria-hidden="true"
        className="sr-only"
      />
      <LoadingButton
        type="submit"
        className={authAction}
        loading={
          signInMutation.isPending && !signInMutation.variables?.autofill
        }
      >
        <KeyRound />
        Sign in with a passkey
      </LoadingButton>
    </form>
  )
}
