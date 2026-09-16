import type { Page } from "@playwright/test"
import { createUser } from "./privateApi.ts"
import { randomEmail, randomPassword } from "./random"
import { logInUser } from "./user"

/** A user of this test's own: the suite shares a database with development. */
export async function newUser(page: Page) {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password })
  await logInUser(page, email, password)
}

/** The REST API as the logged-in user, for setting a scene the way a client would. */
export async function userApi(page: Page) {
  const token = await page.evaluate(() => localStorage.getItem("access_token"))
  const url = `${process.env.VITE_API_URL}/api/v1`
  const headers = { Authorization: `Bearer ${token}` }
  const request = page.request

  const send = async (
    method: "get" | "post" | "patch" | "delete",
    path: string,
    data?: unknown,
  ) => request[method](`${url}${path}`, { headers, data })

  return {
    url,
    headers,
    get: (path: string) => send("get", path),
    post: (path: string, data?: unknown) => send("post", path, data),
    patch: (path: string, data?: unknown) => send("patch", path, data),
    delete: (path: string) => send("delete", path),
    /** POST and return the JSON body, failing loudly if the API refused. */
    create: async (path: string, data?: unknown) => {
      const response = await send("post", path, data)
      if (!response.ok()) {
        throw new Error(`${path} refused: ${await response.text()}`)
      }
      return response.json()
    },
  }
}
