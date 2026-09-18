import { expect, type Page, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"
import { openCaptured } from "./utils/capture"
import { createUser } from "./utils/privateApi.ts"
import { randomEmail, randomPassword } from "./utils/random"

test.use({ storageState: { cookies: [], origins: [] } })

/** Follow a sidebar link, keeping the page — and its cache — alive. */
async function goVia(page: Page, name: string) {
  await page.getByRole("link", { name, exact: true }).first().click()
}

const today = () => {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

test("An edit shows in While you were away without a reload", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  await api.create("/tasks/", { title: "Book the vet", due_date: today() })

  // The log is read once, here; the panel opens over the dashboard from its
  // row, so nothing reloads it but the edit.
  await page.goto("/")
  await expect(page.getByText("Created Book the vet")).toBeVisible()
  await page.getByRole("link", { name: "Book the vet" }).first().click()
  const title = page.getByRole("textbox", { name: "Task title" })
  await title.fill("Book the vet for Friday")
  await title.press("Enter")
  await page.keyboard.press("Escape")

  await expect(
    page.getByText("Changed the title of Book the vet for Friday"),
  ).toBeVisible()
})

test("A captured task counts on the Projects list at once", async ({
  page,
}) => {
  await newUser(page)

  await page.goto("/projects")
  const inbox = page.getByRole("row", { name: /Inbox/ })
  await expect(inbox).toContainText("No tasks")

  // Captured over the list, which lands the task in the Inbox.
  await page.getByRole("button", { name: "Add Task" }).first().click()
  const title = page.getByRole("textbox", { name: "Task title" })
  await title.fill("Prune the roses")
  await title.press("Enter")
  await openCaptured(page)
  await expect(
    page.getByRole("dialog", { name: "Prune the roses" }),
  ).toBeVisible()
  await page.keyboard.press("Escape")

  await expect(inbox).toContainText("1 task")
})

test("Signing in as someone else in the same tab shows none of the first account's data", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  await api.create("/projects/", { name: "First account's secret" })
  await page.goto("/projects")
  await expect(page.getByText("First account's secret")).toBeVisible()

  // Out and in again without reloading, so only the app can forget.
  await page.getByTestId("user-menu").click()
  await page.getByRole("menuitem", { name: "Log out" }).click()
  await page.waitForURL("/login")

  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password })
  await page.getByTestId("email-input").fill(email)
  await page.getByTestId("password-input").fill(password)
  await page.getByRole("button", { name: "Log In" }).click()
  await page.waitForURL("/")

  await goVia(page, "Projects")
  await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible()
  await expect(page.getByRole("row", { name: /Inbox/ })).toBeVisible()
  await expect(page.getByText("First account's secret")).toHaveCount(0)
})
