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

export const createUser = async ({
  email,
  password,
}: {
  email: string
  password: string
}) => {
  const response = await PrivateService.createUser({
    body: {
      email,
      password,
      is_verified: true,
      full_name: "Test User",
    },
  })
  return response.data
}
