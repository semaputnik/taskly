import { test as setup } from "@playwright/test"
import { firstSuperuser } from "./config.ts"
import { createSession } from "./utils/privateApi.ts"

const authFile = "playwright/.auth/user.json"

// The specs run as the superuser unless they say otherwise. The session is
// opened without a passkey ceremony; login.spec.ts and sign-up.spec.ts are
// where signing in itself is tested, through a virtual authenticator.
setup("authenticate", async ({ page }) => {
  const { access_token: token } = await createSession({
    email: firstSuperuser,
    isSuperuser: true,
  })
  await page.goto("/login")
  await page.evaluate(
    (token) => localStorage.setItem("access_token", token),
    token,
  )
  await page.goto("/")
  await page.waitForURL("/")
  await page.context().storageState({ path: authFile })
})
