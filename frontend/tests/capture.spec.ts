import { expect, type Page, test } from "@playwright/test"
import { createUser } from "./utils/privateApi.ts"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

test.use({ storageState: { cookies: [], origins: [] } })

/** A user of this test's own: the suite shares a database with development. */
async function newUser(page: Page) {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password })
  await logInUser(page, email, password)
  return { email, password }
}

async function api(page: Page) {
  const token = await page.evaluate(() => localStorage.getItem("access_token"))
  return {
    url: `${process.env.VITE_API_URL}/api/v1`,
    headers: { Authorization: `Bearer ${token}` },
  }
}

const capturePanel = (page: Page) =>
  page.getByRole("dialog", { name: "New task" })

const titleField = (page: Page) =>
  page.getByRole("textbox", { name: "Task title" })

/** Open capture from the sidebar's Add Task action. */
async function startCapture(page: Page) {
  await page.getByRole("button", { name: "Add Task" }).click()
  await expect(titleField(page)).toBeFocused()
}

test("Capture creates a task from one field and leaves its panel open on it", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/tasks")

  await startCapture(page)
  await titleField(page).fill("Book the dentist")
  await titleField(page).press("Enter")

  // The panel stays, now on the task that exists.
  await expect(page).toHaveURL(/task=[0-9a-f-]{36}/)
  const panel = page.getByRole("dialog", { name: "Book the dentist" })
  await expect(panel).toBeVisible()
  await expect(panel.getByRole("combobox", { name: "Project" })).toContainText(
    "Inbox",
  )

  // And its address survives a reload.
  const url = page.url()
  await page.reload()
  await expect(
    page.getByRole("dialog", { name: "Book the dentist" }),
  ).toBeVisible()
  expect(page.url()).toBe(url)

  // The list behind it holds the task too. It is read with the panel closed:
  // an open panel hides the page behind it from assistive technology, which
  // is what a modal surface is supposed to do.
  await page.keyboard.press("Escape")
  await expect(
    page.getByRole("row", { name: /Book the dentist/ }),
  ).toBeVisible()
})

test("Escape before a title is committed creates nothing", async ({ page }) => {
  await newUser(page)
  await page.goto("/tasks")

  await startCapture(page)
  await titleField(page).press("Escape")
  await expect(capturePanel(page)).toBeHidden()

  // Typing without committing leaves nothing behind either.
  await startCapture(page)
  await titleField(page).fill("Never mind")
  await titleField(page).press("Escape")
  await expect(capturePanel(page)).toBeHidden()

  // Silently: nothing was created, so there is nothing to announce.
  await expect(page.getByText(/created/i)).toHaveCount(0)
  await expect(page.getByText("No tasks yet")).toBeVisible()
  await page.goto("/activity")
  await expect(
    page.getByText("Nothing has happened in your account yet."),
  ).toBeVisible()
})

test("Closing the panel after the title is committed leaves the task in place", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/tasks")

  await startCapture(page)
  await titleField(page).fill("Renew the passport")
  await titleField(page).press("Enter")
  await expect(
    page.getByRole("dialog", { name: "Renew the passport" }),
  ).toBeVisible()

  await page.keyboard.press("Escape")
  await expect(page.getByRole("dialog")).toBeHidden()
  await expect(page).not.toHaveURL(/task=/)
  await expect(
    page.getByRole("row", { name: /Renew the passport/ }),
  ).toBeVisible()
})

test("A property set straight after capture persists with no Save", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/tasks")

  await startCapture(page)
  await titleField(page).fill("File the tax return")
  await titleField(page).press("Enter")

  const panel = page.getByRole("dialog", { name: "File the tax return" })
  await panel.getByRole("combobox", { name: "Priority" }).click()
  await page.getByRole("option", { name: "P1" }).click()

  await page.reload()
  await expect(
    page
      .getByRole("dialog", { name: "File the tax return" })
      .getByRole("combobox", { name: "Priority" }),
  ).toContainText("P1")
})

test("Capture lands in the project the list is filtered to, and in Inbox otherwise", async ({
  page,
}) => {
  await newUser(page)
  const { url, headers } = await api(page)
  for (const name of ["Kitchen rebuild", "Shelved"]) {
    const created = await page.request.post(`${url}/projects/`, {
      headers,
      data: { name },
    })
    expect(created.ok()).toBe(true)
  }

  await page.goto("/tasks")
  await page.getByRole("button", { name: "Filters" }).click()
  await page.getByRole("combobox", { name: "Project" }).first().click()
  await page.getByRole("option", { name: "Kitchen rebuild" }).click()
  await expect(page).toHaveURL(/project_id=/)

  await startCapture(page)
  await expect(capturePanel(page)).toContainText("Kitchen rebuild")
  await titleField(page).fill("Measure the alcove")
  await titleField(page).press("Enter")
  await expect(
    page
      .getByRole("dialog", { name: "Measure the alcove" })
      .getByRole("combobox", { name: "Project" }),
  ).toContainText("Kitchen rebuild")

  // Unfiltered, the default is Inbox again.
  await page.goto("/tasks")
  await startCapture(page)
  await expect(capturePanel(page)).toContainText("Inbox")
  await titleField(page).fill("Pick up the parcel")
  await titleField(page).press("Enter")
  await expect(
    page
      .getByRole("dialog", { name: "Pick up the parcel" })
      .getByRole("combobox", { name: "Project" }),
  ).toContainText("Inbox")
})

test("An archived project is never a capture context", async ({ page }) => {
  await newUser(page)
  const { url, headers } = await api(page)
  const project = await (
    await page.request.post(`${url}/projects/`, {
      headers,
      data: { name: "Old house" },
    })
  ).json()
  expect(
    (
      await page.request.post(`${url}/projects/${project.id}/archive`, {
        headers,
      })
    ).ok(),
  ).toBe(true)

  await page.goto(`/tasks?project_id=${project.id}`)
  await startCapture(page)
  await expect(capturePanel(page)).toContainText("Inbox")
  await titleField(page).fill("Sort the loft")
  await titleField(page).press("Enter")
  await expect(
    page
      .getByRole("dialog", { name: "Sort the loft" })
      .getByRole("combobox", { name: "Project" }),
  ).toContainText("Inbox")
})

test("The keyboard opens capture, and a run of them costs one gesture each", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/")
  // The shell has to be listening before a key means anything to it.
  await expect(page.getByRole("button", { name: "Add Task" })).toBeVisible()

  // From the dashboard, with no mouse.
  await page.keyboard.press("c")
  await expect(titleField(page)).toBeFocused()

  // The chord commits and keeps capture open for the next thought.
  await titleField(page).fill("Water the plants")
  await titleField(page).press("ControlOrMeta+Enter")
  await expect(titleField(page)).toHaveValue("")
  await expect(titleField(page)).toBeFocused()
  await titleField(page).fill("Call the plumber")
  await titleField(page).press("Enter")

  await expect(
    page.getByRole("dialog", { name: "Call the plumber" }),
  ).toBeVisible()
  await page.goto("/tasks")
  await expect(
    page.getByRole("row", { name: /Water the plants/ }),
  ).toBeVisible()
  await expect(
    page.getByRole("row", { name: /Call the plumber/ }),
  ).toBeVisible()
})

test("The shortcut never steals a keystroke from a field being typed into", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/projects")

  await page.getByRole("button", { name: "Add Project" }).click()
  const name = page.getByPlaceholder("Project name")
  await name.fill("Coastal route")
  await name.press("c")
  await expect(capturePanel(page)).toBeHidden()
  await expect(name).toHaveValue("Coastal routec")
})

test("A subtask is captured from its parent's Subtasks tab", async ({
  page,
}) => {
  await newUser(page)
  const { url, headers } = await api(page)
  const project = await (
    await page.request.post(`${url}/projects/`, {
      headers,
      data: { name: "Move house" },
    })
  ).json()
  const parent = await (
    await page.request.post(`${url}/tasks/`, {
      headers,
      data: { title: "Pack the study", project_id: project.id },
    })
  ).json()

  await page.goto(`/tasks?task=${parent.id}`)
  const panel = page.getByRole("dialog", { name: "Pack the study" })
  await panel.getByRole("tab", { name: "Subtasks" }).click()
  const subtaskField = panel.getByRole("textbox", { name: "Subtask title" })
  await subtaskField.fill("Empty the desk drawers")
  await subtaskField.press("Enter")

  // The parent stays in view with the child under it.
  await expect(
    panel.getByRole("button", { name: "Empty the desk drawers" }),
  ).toBeVisible()
  await expect(subtaskField).toHaveValue("")
  await expect(page).toHaveURL(new RegExp(`task=${parent.id}`))

  // The child follows its parent's project rather than owning one.
  await panel.getByRole("button", { name: "Empty the desk drawers" }).click()
  const child = page.getByRole("dialog", { name: "Empty the desk drawers" })
  await expect(child).toContainText("Follows its parent task")
  await expect(child).toContainText(
    "Only a task at the top of its tree can repeat",
  )
})

test("A captured task is one creation entry in the activity log", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/tasks")

  await startCapture(page)
  await titleField(page).fill("Return the library books")
  await titleField(page).press("Enter")
  await expect(
    page.getByRole("dialog", { name: "Return the library books" }),
  ).toBeVisible()

  await page.goto("/activity")
  await expect(
    page.getByRole("row", { name: /Return the library books/ }),
  ).toHaveCount(1)
  await expect(
    page.getByRole("row", { name: /Return the library books/ }),
  ).toContainText("Created")
})

test("A refused creation keeps what was typed and says what failed", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/tasks")

  await startCapture(page)
  const tooLong = "x".repeat(300)
  await titleField(page).fill(tooLong)
  await titleField(page).press("Enter")

  await expect(page.getByText(/at most 255 characters/i)).toBeVisible()
  await expect(titleField(page)).toHaveValue(tooLong)
  await expect(page).not.toHaveURL(/task=/)
})
