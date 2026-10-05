import { expect, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

test("A comment draft survives following a subtask", async ({ page }) => {
  await newUser(page)
  const api = await userApi(page)
  const task = await api.create("/tasks/", { title: "Move house" })
  await api.create("/tasks/", { title: "Pack the books", parent_id: task.id })

  await page.goto(`/tasks?view=table&task=${task.id}`)
  const panel = page.getByRole("complementary", { name: "Move house" })
  const draft = panel.getByPlaceholder("Write a comment…")
  await draft.fill("Movers booked for the 12th, still need")

  // Opening a subtask and coming back through the breadcrumb costs nothing.
  await panel.getByRole("button", { name: "Pack the books" }).click()
  const child = page.getByRole("complementary", { name: "Pack the books" })
  await expect(child.getByPlaceholder("Write a comment…")).toHaveValue("")
  await child.getByRole("button", { name: "Move house" }).click()

  await expect(draft).toHaveValue("Movers booked for the 12th, still need")
  // Focus comes back to where the typing stopped.
  await draft.focus()
  await page.keyboard.type(" boxes")

  // Posting still sends it once and clears the field.
  const posted = page.waitForResponse(
    (r) => r.url().includes("/comments/") && r.request().method() === "POST",
  )
  await panel.getByRole("button", { name: "Comment", exact: true }).click()
  await posted
  await expect(draft).toHaveValue("")
  const thread = await (await api.get(`/tasks/${task.id}/comments/`)).json()
  expect(thread.data.map((c: { body: string }) => c.body)).toEqual([
    "Movers booked for the 12th, still need boxes",
  ])
})

test("Opening a task fetches its files once, with the rest of the task", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const task = await api.create("/tasks/", { title: "Move house" })

  const attachmentRequests: string[] = []
  page.on("request", (r) => {
    if (r.url().includes("/attachments/")) attachmentRequests.push(r.url())
  })
  await page.goto(`/tasks?view=table&task=${task.id}`)
  const panel = page.getByRole("complementary", { name: "Move house" })
  await expect(panel.getByRole("region", { name: "Activity" })).toBeVisible()
  await expect(
    panel.getByRole("button", { name: "Attach a file" }),
  ).toBeVisible()
  expect(attachmentRequests).toHaveLength(1)
})
