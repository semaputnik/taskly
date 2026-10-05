import {
  type AuthenticationResponseJSON,
  browserSupportsWebAuthn,
  browserSupportsWebAuthnAutofill,
  type PublicKeyCredentialCreationOptionsJSON,
  type PublicKeyCredentialRequestOptionsJSON,
  type RegistrationResponseJSON,
  startAuthentication,
  startRegistration,
  WebAuthnAbortService,
} from "@simplewebauthn/browser"

import { LoginService, UsersService } from "@/client"
import { toastError } from "@/lib/toasts"

/**
 * Passkey ceremonies, end to end: ask the API for options, hand them to the
 * browser, and send the browser's answer back (F-12).
 *
 * Every way in and every change that needs a fresh confirmation goes through
 * here, so the rest of the app asks for an outcome — a session token, a
 * confirmation, a new passkey — and never handles WebAuthn itself.
 */

/** Whether this browser can sign in at all. Without it there is no way in (FR-12.12). */
export function passkeysSupported(): boolean {
  return browserSupportsWebAuthn()
}

/** Whether the browser offers passkeys in the email field's autofill (FR-12.3). */
export function autofillSupported(): Promise<boolean> {
  return browserSupportsWebAuthnAutofill()
}

/** Stop a ceremony that is waiting, such as the autofill one, before starting another. */
export function cancelCeremony() {
  WebAuthnAbortService.cancelCeremony()
}

/**
 * Whether a ceremony failed because the person dismissed the browser's prompt
 * or it was cancelled for another ceremony: not a problem to report.
 */
export function wasDismissed(error: unknown): boolean {
  if (!(error instanceof Error)) return false
  const code = (error as { code?: string }).code
  return (
    error.name === "NotAllowedError" ||
    error.name === "AbortError" ||
    code === "ERROR_CEREMONY_ABORTED"
  )
}

/** Report a failed ceremony, unless the person just dismissed the prompt. */
export function reportUnlessDismissed(error: unknown) {
  if (!wasDismissed(error)) toastError(error)
}

const creationOptions = (data: unknown) =>
  data as PublicKeyCredentialCreationOptionsJSON
const requestOptions = (data: unknown) =>
  data as PublicKeyCredentialRequestOptionsJSON
const asCredential = (
  response: RegistrationResponseJSON | AuthenticationResponseJSON,
) => response as unknown as Record<string, unknown>

/** Create an account with its first passkey, and sign in (FR-12.2). */
export async function registerAccount(email: string): Promise<string> {
  const { data: options } = await LoginService.registrationOptions({
    body: { email },
  })
  const response = await startRegistration({
    optionsJSON: creationOptions(options),
  })
  const { data } = await LoginService.register({
    body: { credential: asCredential(response) },
  })
  return data.access_token
}

/**
 * Sign in with whatever passkey the browser offers (FR-12.3). With
 * `autofill`, the browser offers them in the email field's suggestions and
 * the promise waits until one is picked.
 */
export async function signInWithPasskey({
  autofill = false,
}: {
  autofill?: boolean
} = {}): Promise<string> {
  const { data: options } = await LoginService.signInOptions()
  const response = await startAuthentication({
    optionsJSON: requestOptions(options),
    useBrowserAutofill: autofill,
  })
  const { data } = await LoginService.signIn({
    body: { credential: asCredential(response) },
  })
  return data.access_token
}

/**
 * A fresh confirmation with one of the signed-in user's passkeys, for a
 * change the session alone may not make (FR-12.7, FR-12.16).
 */
export async function confirmWithPasskey(): Promise<Record<string, unknown>> {
  const { data: options } = await UsersService.confirmationOptions()
  const response = await startAuthentication({
    optionsJSON: requestOptions(options),
  })
  return asCredential(response)
}

/** Add a passkey to the signed-in account, after confirming with one it holds. */
export async function addPasskey() {
  const confirmation = await confirmWithPasskey()
  const { data: options } = await UsersService.newPasskeyOptions({
    body: { confirmation },
  })
  const response = await startRegistration({
    optionsJSON: creationOptions(options),
  })
  const { data } = await UsersService.addPasskey({
    body: { credential: asCredential(response) },
  })
  return data
}

/** Remove one of the signed-in account's passkeys, after confirming. */
export async function removePasskey(passkeyId: string) {
  const confirmation = await confirmWithPasskey()
  await UsersService.removePasskey({
    path: { passkey_id: passkeyId },
    body: { confirmation },
  })
}

/** The superuser issuing a recovery code for another user, after confirming. */
export async function issueRecoveryCode(userId: string) {
  const confirmation = await confirmWithPasskey()
  const { data } = await UsersService.issueRecoveryCode({
    path: { user_id: userId },
    body: { confirmation },
  })
  return data
}

/**
 * Spend a recovery code on a new passkey, and sign in (FR-12.17). Every other
 * session of the account ends (FR-12.14).
 */
export async function recoverAccount(
  email: string,
  code: string,
): Promise<string> {
  const { data: options } = await LoginService.recoveryOptions({
    body: { email, code },
  })
  const response = await startRegistration({
    optionsJSON: creationOptions(options),
  })
  const { data } = await LoginService.recover({
    body: { credential: asCredential(response) },
  })
  return data.access_token
}
