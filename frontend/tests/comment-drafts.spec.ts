import { expect, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

test("A comment draft survives switching tabs and following a subtask", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const task = await api.create("/tasks/", { title: "Move house" })
  await api.create("/tasks/", { title: "Pack the books", parent_id: task.id })

  await page.goto(`/tasks?task=${task.id}`)
  const panel = page.getByRole("dialog", { name: "Move house" })
  const draft = panel.getByPlaceholder("Add a comment")
  await draft.fill("Movers booked for the 12th, still need")

  // A look at the subtasks costs nothing.
  await panel.getByRole("tab", { name: /Subtasks/ }).click()
  await expect(draft).toHaveCount(0)
  // Nor does opening one and coming back through the breadcrumb.
  await panel.getByRole("button", { name: "Pack the books" }).click()
  const child = page.getByRole("dialog", { name: "Pack the books" })
  await expect(child.getByPlaceholder("Add a comment")).toHaveValue("")
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

  // And the posted text is not waiting as a draft when the tab comes back.
  await panel.getByRole("tab", { name: "Files" }).click()
  await panel.getByRole("tab", { name: "Comments" }).click()
  await expect(draft).toHaveValue("")
})

test("Only the tab on screen fetches its collection", async ({ page }) => {
  await newUser(page)
  const api = await userApi(page)
  const task = await api.create("/tasks/", { title: "Move house" })

  const attachmentRequests: string[] = []
  page.on("request", (r) => {
    if (r.url().includes("/attachments/")) attachmentRequests.push(r.url())
  })
  await page.goto(`/tasks?task=${task.id}`)
  const panel = page.getByRole("dialog", { name: "Move house" })
  await expect(panel.getByText("No comments yet.")).toBeVisible()
  expect(attachmentRequests).toEqual([])

  await panel.getByRole("tab", { name: "Files" }).click()
  await expect(panel.getByText("No attachments yet.")).toBeVisible()
  expect(attachmentRequests).toHaveLength(1)
})
