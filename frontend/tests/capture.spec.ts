import { expect, type Page, test } from "@playwright/test"
import {
  carryOver,
  draftToCreate,
  emptyDraft,
  isTouched,
} from "../src/components/Tasks/draft"
import { openCaptured } from "./utils/capture"
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

test("Capture creates a task from one field, closes, and offers the way to it", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/tasks?view=table")

  await startCapture(page)
  await titleField(page).fill("Book the dentist")
  await titleField(page).press("Enter")

  // A single capture is done: the panel closes on the list it opened over,
  // and the list holds the task.
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await expect(page).not.toHaveURL(/capture=|task=/)
  await expect(
    page.getByRole("row", { name: /Book the dentist/ }),
  ).toBeVisible()

  // The notice is the receipt, and opens what was made.
  const notice = page.getByText("“Book the dentist” created")
  await expect(notice).toBeVisible()
  await page.getByRole("button", { name: "Open" }).click()
  await expect(page).toHaveURL(/task=[0-9a-f-]{36}/)
  const panel = page.getByRole("dialog", { name: "Book the dentist" })
  await expect(panel).toBeVisible()
  await expect(panel.getByRole("combobox", { name: "Project" })).toContainText(
    "Inbox",
  )
})

test("Escape before a title is committed creates nothing", async ({ page }) => {
  await newUser(page)
  await page.goto("/tasks?view=table")

  await startCapture(page)
  await titleField(page).press("Escape")
  await expect(capturePanel(page)).toBeHidden()

  // Typing without committing leaves nothing behind either, once the
  // reader says the draft can go.
  await startCapture(page)
  await titleField(page).fill("Never mind")
  await titleField(page).press("Escape")
  await page
    .getByRole("dialog", { name: "Discard this task?" })
    .getByRole("button", { name: "Discard" })
    .click()
  await expect(capturePanel(page)).toBeHidden()

  // Silently: nothing was created, so there is nothing to announce. Asked of
  // the notices rather than of the page, which has a Created column of its
  // own to say when each task was filed.
  await expect(page.locator("[data-sonner-toast]")).toHaveCount(0)
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
  await page.goto("/tasks?view=table")

  await startCapture(page)
  await titleField(page).fill("Renew the passport")
  await titleField(page).press("Enter")
  await openCaptured(page)
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
  await page.goto("/tasks?view=table")

  await startCapture(page)
  await titleField(page).fill("File the tax return")
  await titleField(page).press("Enter")
  await openCaptured(page)

  const panel = page.getByRole("dialog", { name: "File the tax return" })
  await panel.getByRole("combobox", { name: "Priority" }).click()
  // No Save: choosing is the write. It is waited for, not raced by the reload.
  const saved = page.waitForResponse(
    (response) => response.request().method() === "PATCH",
  )
  await page.getByRole("option", { name: "P1" }).click()
  await saved

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

  await page.goto("/tasks?view=table")
  await page.getByRole("button", { name: "Filters" }).click()
  await page.getByRole("combobox", { name: "Project" }).first().click()
  await page.getByRole("option", { name: "Kitchen rebuild" }).click()
  await expect(page).toHaveURL(/project_id=/)

  await startCapture(page)
  await expect(capturePanel(page)).toContainText("Kitchen rebuild")
  await titleField(page).fill("Measure the alcove")
  await titleField(page).press("Enter")
  await openCaptured(page)
  await expect(
    page
      .getByRole("dialog", { name: "Measure the alcove" })
      .getByRole("combobox", { name: "Project" }),
  ).toContainText("Kitchen rebuild")

  // Unfiltered, the default is Inbox again.
  await page.goto("/tasks?view=table")
  await startCapture(page)
  await expect(capturePanel(page)).toContainText("Inbox")
  await titleField(page).fill("Pick up the parcel")
  await titleField(page).press("Enter")
  await openCaptured(page)
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

  await page.goto(`/tasks?view=table&project_id=${project.id}`)
  await startCapture(page)
  await expect(capturePanel(page)).toContainText("Inbox")
  await titleField(page).fill("Sort the loft")
  await titleField(page).press("Enter")
  await openCaptured(page)
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
  await openCaptured(page)

  await expect(
    page.getByRole("dialog", { name: "Call the plumber" }),
  ).toBeVisible()
  await page.goto("/tasks?view=table")
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

  // The project panel's own name field is a field like any other: the key
  // that starts capture is a letter in it.
  await page.getByRole("button", { name: "Add Project" }).click()
  const name = page.getByRole("textbox", { name: "Project name" })
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

  await page.goto(`/tasks?view=table&task=${parent.id}`)
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
  await page.goto("/tasks?view=table")

  await startCapture(page)
  await titleField(page).fill("Return the library books")
  await titleField(page).press("Enter")
  await openCaptured(page)
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
  await page.goto("/tasks?view=table")

  await startCapture(page)
  const tooLong = "x".repeat(300)
  await titleField(page).fill(tooLong)
  await titleField(page).press("Enter")

  await expect(page.getByText(/at most 255 characters/i)).toBeVisible()
  await expect(titleField(page)).toHaveValue(tooLong)
  await expect(page).not.toHaveURL(/task=/)
})

// --- The draft ----------------------------------------------------------------

test("A draft becomes one create request, and a subtask sends no project or rule", () => {
  const draft = {
    ...emptyDraft({ projectId: "p1" }),
    title: "  Send the invoice ",
    description: "",
    due_date: "2026-10-02",
    priority: "P2" as const,
    assignee: "me",
    tags: ["finance"],
    recurrence: { frequency: "weekly" as const },
  }
  expect(draftToCreate(draft, { projectId: "p1" }, "u1")).toEqual({
    title: "Send the invoice",
    description: null,
    due_date: "2026-10-02",
    priority: "P2",
    assignee_id: "u1",
    tags: ["finance"],
    project_id: "p1",
    recurrence: { frequency: "weekly" },
  })
  const subtask = draftToCreate(draft, { parentId: "t1" }, "u1")
  expect(subtask.parent_id).toBe("t1")
  expect(subtask).not.toHaveProperty("project_id")
  expect(subtask).not.toHaveProperty("recurrence")
})

test("A run carries the properties and clears the words, and touched follows the carried defaults", () => {
  const start = emptyDraft({})
  expect(isTouched(start, start)).toBe(false)
  expect(isTouched({ ...start, title: "x" }, start)).toBe(true)
  expect(isTouched({ ...start, description: "x" }, start)).toBe(true)
  expect(isTouched({ ...start, tags: ["a"] }, start)).toBe(true)

  const filled = {
    ...start,
    title: "One",
    description: "notes",
    project_id: "p2",
    due_date: "2026-10-02",
    priority: "P1" as const,
    assignee: "bot",
    tags: ["a"],
    recurrence: { frequency: "daily" as const },
  }
  const next = carryOver(filled)
  expect(next).toEqual({ ...filled, title: "", description: "" })
  // After a run, the carried values are what "untouched" means.
  expect(isTouched(next, next)).toBe(false)
  expect(isTouched({ ...next, priority: null }, next)).toBe(true)
})

test("Capture opens every property row, no tabs, and sends nothing while filled in", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/tasks?view=table")

  const writes: string[] = []
  page.on("request", (request) => {
    if (request.method() !== "GET") writes.push(request.url())
  })

  await startCapture(page)
  const panel = capturePanel(page)
  await expect(panel).toContainText("Not saved yet")
  for (const name of ["Project", "Priority", "Assignee", "Repeat"]) {
    await expect(panel.getByRole("combobox", { name })).toBeVisible()
  }
  await expect(panel.getByRole("button", { name: /Due date/ })).toBeVisible()
  await expect(panel.getByRole("button", { name: "Add tag" })).toBeVisible()
  await expect(
    panel.getByRole("textbox", { name: "Task description" }),
  ).toBeVisible()
  await expect(panel.getByRole("tab")).toHaveCount(0)
  await expect(panel.getByText("Status", { exact: true })).toHaveCount(0)
  await expect(panel.getByRole("checkbox")).toHaveCount(0)
  const create = panel.getByRole("button", { name: "Create task" })
  await expect(create).toBeDisabled()

  await titleField(page).fill("Send the invoice")
  await panel.getByRole("combobox", { name: "Priority" }).click()
  await page.getByRole("option", { name: "P2" }).click()
  await panel.getByRole("button", { name: "Add tag" }).click()
  await page
    .getByRole("combobox", { name: "Search or create a tag" })
    .fill("finance")
  await page.getByRole("option", { name: 'Create tag "finance"' }).click()
  await page.keyboard.press("Escape")
  await panel.getByRole("textbox", { name: "Task description" }).fill("For Q3")

  expect(writes).toEqual([])
  await expect(create).toBeEnabled()
})

test("Enter creates the whole draft as one task and one log entry", async ({
  page,
}) => {
  await newUser(page)
  const { url, headers } = await api(page)
  const project = await (
    await page.request.post(`${url}/projects/`, {
      headers,
      data: { name: "Accounts" },
    })
  ).json()
  await page.goto("/tasks?view=table")

  await startCapture(page)
  const panel = capturePanel(page)
  await panel.getByRole("combobox", { name: "Project" }).click()
  await page.getByRole("option", { name: "Accounts" }).click()
  await panel.getByRole("combobox", { name: "Priority" }).click()
  await page.getByRole("option", { name: "P2" }).click()
  await panel.getByRole("button", { name: "Add tag" }).click()
  await page
    .getByRole("combobox", { name: "Search or create a tag" })
    .fill("finance")
  await expect(
    page.getByRole("option", { name: 'Create tag "finance"' }),
  ).toBeVisible()
  await page.keyboard.press("Enter")
  await page.keyboard.press("Escape")
  await titleField(page).fill("Send the invoice")

  const creates: unknown[] = []
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/tasks/")) {
      creates.push(request.postDataJSON())
    }
  })
  await titleField(page).press("Enter")
  await openCaptured(page)

  const record = page.getByRole("dialog", { name: "Send the invoice" })
  await expect(record).toBeVisible()
  await expect(record.getByRole("combobox", { name: "Project" })).toContainText(
    "Accounts",
  )
  await expect(
    record.getByRole("combobox", { name: "Priority" }),
  ).toContainText("P2")
  await expect(
    record.getByRole("button", { name: "Remove tag finance" }),
  ).toBeVisible()
  // What only a record has joins it.
  await expect(record.getByRole("tab", { name: "Comments" })).toBeVisible()
  await expect(record.getByRole("combobox", { name: "Status" })).toBeVisible()
  expect(creates).toHaveLength(1)
  expect(creates[0]).toMatchObject({
    project_id: project.id,
    priority: "P2",
    tags: ["finance"],
  })

  await page.goto("/activity")
  const entries = page.getByRole("row", { name: /Send the invoice/ })
  await expect(entries).toHaveCount(1)
  await expect(entries).toContainText("Created Send the invoice in Accounts")
})

test("The chord from the description creates, clears the words and keeps the settings", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/tasks?view=table")

  await startCapture(page)
  const panel = capturePanel(page)
  await panel.getByRole("combobox", { name: "Priority" }).click()
  await page.getByRole("option", { name: "P1" }).click()
  await panel.locator('input[type="date"]').fill("2031-10-02")
  await panel.getByRole("button", { name: "Add tag" }).click()
  await page
    .getByRole("combobox", { name: "Search or create a tag" })
    .fill("errands")
  await expect(
    page.getByRole("option", { name: 'Create tag "errands"' }),
  ).toBeVisible()
  await page.keyboard.press("Enter")
  await page.keyboard.press("Escape")

  await titleField(page).fill("Buy stamps")
  const description = panel.getByRole("textbox", { name: "Task description" })
  await description.fill("First line")
  // Plain Enter is a new line in the description.
  await description.press("Enter")
  await description.pressSequentially("second")
  await expect(description).toHaveValue("First line\nsecond")
  await description.press("ControlOrMeta+Enter")

  await expect(titleField(page)).toHaveValue("")
  await expect(titleField(page)).toBeFocused()
  await expect(description).toHaveValue("")
  await expect(panel.getByRole("combobox", { name: "Priority" })).toContainText(
    "P1",
  )
  await expect(
    panel.getByRole("button", { name: "Remove tag errands" }),
  ).toBeVisible()
  await expect(page.getByText("Buy stamps created")).toBeAttached()

  await titleField(page).fill("Post the letter")
  await titleField(page).press("ControlOrMeta+Enter")
  await expect(titleField(page)).toHaveValue("")

  // Closing after the run asks nothing: the carried values are the defaults.
  await page.keyboard.press("Escape")
  await expect(capturePanel(page)).toBeHidden()
  await expect(page.getByRole("dialog")).toHaveCount(0)

  for (const title of ["Buy stamps", "Post the letter"]) {
    const row = page.getByRole("row", { name: new RegExp(title) })
    await expect(row).toContainText("P1")
    await expect(row).toContainText("errands")
    await expect(row).toContainText("2031")
  }
})

test("A touched draft asks before it goes, however it is closed", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/tasks?view=table")

  await startCapture(page)
  const panel = capturePanel(page)
  await panel.getByRole("combobox", { name: "Priority" }).click()
  await page.getByRole("option", { name: "P3" }).click()
  await expect(page.getByRole("listbox")).toBeHidden()

  const confirm = page.getByRole("dialog", { name: "Discard this task?" })
  await page.keyboard.press("Escape")
  await expect(confirm).toBeVisible()
  // The safe choice is in hand, and Escape keeps editing.
  await expect(
    confirm.getByRole("button", { name: "Keep editing" }),
  ).toBeFocused()
  await page.keyboard.press("Escape")
  await expect(confirm).toBeHidden()
  await expect(panel.getByRole("combobox", { name: "Priority" })).toContainText(
    "P3",
  )

  await titleField(page).fill("Half a thought")
  await panel.getByRole("button", { name: "Close" }).click()
  await expect(confirm).toBeVisible()
  await confirm.getByRole("button", { name: "Keep editing" }).click()
  await expect(titleField(page)).toHaveValue("Half a thought")
  await expect(page).toHaveURL(/capture=task/)

  // Back is a way out too.
  await page.goBack()
  await expect(confirm).toBeVisible()
  await confirm.getByRole("button", { name: "Discard" }).click()
  await expect(capturePanel(page)).toBeHidden()
  await expect(page.getByText("No tasks yet")).toBeVisible()
})

test("A refused create keeps every field of the draft", async ({ page }) => {
  await newUser(page)
  await page.goto("/tasks?view=table")

  await startCapture(page)
  const panel = capturePanel(page)
  // A repeating task needs a due date, so the API refuses this one.
  await panel.getByRole("combobox", { name: "Repeat" }).click()
  await page.getByRole("option", { name: "Every week" }).click()
  await panel.getByRole("combobox", { name: "Priority" }).click()
  await page.getByRole("option", { name: "P4" }).click()
  await panel.getByRole("textbox", { name: "Task description" }).fill("Notes")
  await titleField(page).fill("Water the plants")
  await panel.getByRole("button", { name: "Create task" }).click()

  await expect(
    page.getByText("A recurring task needs a due date"),
  ).toBeVisible()
  await expect(capturePanel(page)).toBeVisible()
  await expect(titleField(page)).toHaveValue("Water the plants")
  await expect(panel.getByRole("combobox", { name: "Repeat" })).toContainText(
    "Every week",
  )
  await expect(panel.getByRole("combobox", { name: "Priority" })).toContainText(
    "P4",
  )
  await expect(
    panel.getByRole("textbox", { name: "Task description" }),
  ).toHaveValue("Notes")
})

test.describe("on a phone", () => {
  test.use({
    viewport: { width: 375, height: 667 },
    hasTouch: true,
    isMobile: true,
  })

  test("Create task is on screen without scrolling", async ({ page }) => {
    await newUser(page)
    await page.goto("/tasks?view=table")
    await page.goto("/tasks?view=table&capture=task")
    await expect(titleField(page)).toBeVisible()
    const create = capturePanel(page).getByRole("button", {
      name: "Create task",
    })
    await expect(create).toBeInViewport({ ratio: 1 })
  })
})
