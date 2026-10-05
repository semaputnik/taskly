import { expect, type Page, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"
import { randomEmail } from "./utils/random"
import { taskLine } from "./utils/tasks"
import { logInUser } from "./utils/user"

test.use({ storageState: { cookies: [], origins: [] } })

const UNKNOWN = "00000000-0000-4000-8000-000000000000"

async function expectCannotOpen(page: Page, route: string, search: string) {
  await page.goto(`${route}?${search}`)
  const panel = page.locator("[data-record-column]")
  // Said at once, not after a run of retries behind a skeleton.
  await expect(panel).toContainText("could not be opened", { timeout: 2_000 })
  await expect(panel.locator("[data-slot=skeleton]")).toHaveCount(0)
  await expect(panel.getByRole("button", { name: "Try again" })).toHaveCount(0)

  // The way out clears the record from the address and leaves the screen.
  await panel
    .getByRole("button", { name: "Close", exact: true })
    .first()
    .click()
  await expect(page.locator("[data-record-column]")).toHaveCount(0)
  await expect(page).toHaveURL(new RegExp(`${route}$`))
}

test("A link to a record that is not there says so, for every panel", async ({
  page,
}) => {
  await newUser(page)

  await expectCannotOpen(page, "/tasks", `task=${UNKNOWN}`)
  await expectCannotOpen(page, "/projects", `project=${UNKNOWN}`)
  await expectCannotOpen(page, "/tags", `tag_id=${UNKNOWN}`)
  await expectCannotOpen(page, "/bots", `bot=${UNKNOWN}`)
  // Something that is not an id at all is not a record to open: the screen
  // behind it simply shows, with nothing left waiting.
  await page.goto("/tasks?task=not-a-task")
  await expect(page.getByRole("heading", { name: "Tasks" })).toBeVisible()
  await expect(page.locator("[data-record-column]")).toHaveCount(0)
})

test("Another user's record reads exactly like a missing one", async ({
  page,
}) => {
  await newUser(page)
  const theirs = await (await userApi(page)).create("/tasks/", {
    title: "Private plans",
  })

  const email = randomEmail()
  await page.evaluate(() => localStorage.removeItem("access_token"))
  await logInUser(page, email)

  await expectCannotOpen(page, "/tasks", `task=${theirs.id}`)
  await expect(page.getByText("Private plans")).toHaveCount(0)
})

test("A failure that may pass offers to try again", async ({ page }) => {
  await newUser(page)
  const task = await (await userApi(page)).create("/tasks/", {
    title: "Book the vet",
  })

  // The request is let through by the press of Try again and by nothing
  // else, not by a timer in the test: the query's own retry would load the
  // task the moment the API answered, and take the button away before it is
  // pressed. The page marks the press itself, before the button's own handler
  // asks again.
  await page.addInitScript(() => {
    window.addEventListener(
      "click",
      (event) => {
        const target = event.target as Element | null
        if (target?.closest("button")?.textContent === "Try again") {
          ;(window as unknown as { pressedTryAgain: boolean }).pressedTryAgain =
            true
        }
      },
      true,
    )
  })
  const pressed = () =>
    page
      .evaluate(
        () =>
          (window as unknown as { pressedTryAgain?: boolean }).pressedTryAgain,
      )
      // Asked while the page is still loading: not pressed yet.
      .catch(() => false)
  await page.route(`**/api/v1/tasks/${task.id}`, async (route) =>
    (await pressed())
      ? route.fallback()
      : route.fulfill({ status: 503, body: "unavailable" }),
  )
  await page.goto(`/tasks?task=${task.id}`)
  const panel = page.locator("[data-record-column]")
  // Said after the first failed attempt, while retries carry on behind it.
  await expect(panel).toContainText("could not be loaded", { timeout: 3_000 })
  await expect(panel.locator("[data-slot=skeleton]")).toHaveCount(0)

  await panel.getByRole("button", { name: "Try again" }).click()
  await expect(
    page.getByRole("complementary", { name: "Book the vet" }),
  ).toBeVisible()
  await expect(page.getByRole("textbox", { name: "Task title" })).toHaveValue(
    "Book the vet",
  )
})

test("A task the list filters out still opens from its link", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const project = await api.create("/projects/", { name: "Garden" })
  const task = await api.create("/tasks/", {
    title: "Prune the roses",
    project_id: project.id,
  })
  const inbox = (await (await api.get("/projects/")).json()).data.find(
    (p: { is_inbox: boolean }) => p.is_inbox,
  )

  await page.goto(`/tasks?project_id=${inbox.id}&task=${task.id}`)
  await expect(
    page.getByRole("complementary", { name: "Prune the roses" }),
  ).toBeVisible()
  await expect(taskLine(page, "Prune the roses")).toHaveCount(0)
})
