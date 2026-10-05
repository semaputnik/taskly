// Note: the `PrivateService` is only available when generating the client
// for local environments
import { Agent } from "node:http"
import { PrivateService } from "../../src/client"
import { client } from "../../src/client/client.gen"

client.setConfig({
  baseURL: `${process.env.VITE_API_URL}`,
  // A fresh connection per request. Node keeps connections alive by default,
  // and the backend closes one that has been idle for five seconds: a request
  // sent down it in that moment fails with "socket hang up", which a test
  // waiting between steps can hit.
  httpAgent: new Agent({ keepAlive: false }),
})

/**
 * A user and a session for them, without a passkey ceremony: the way a test
 * sets a scene when signing in is not what it is about. An existing user is
 * signed in as they are.
 */
export const createSession = async ({
  email,
  isSuperuser = false,
}: {
  email: string
  isSuperuser?: boolean
}) => {
  const response = await PrivateService.createUser({
    body: { email, full_name: "Test User", is_superuser: isSuperuser },
  })
  return response.data
}

export const createUser = async (user: {
  email: string
  isSuperuser?: boolean
}) => (await createSession(user)).user

/** A recovery code for the user, as the server's recovery command prints one. */
export const recoveryCodeFor = async (email: string) => {
  const response = await PrivateService.issueRecoveryCode({ body: { email } })
  return response.data.code
}
