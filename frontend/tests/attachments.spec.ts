import { expect, type Page, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"

test.use({ storageState: { cookies: [], origins: [] } })

/** A task holding one attachment, open on its Files tab. */
async function openFiles(page: Page) {
  await newUser(page)
  const api = await userApi(page)
  const task = await api.create("/tasks/", { title: "File the taxes" })
  const uploaded = await page.request.post(
    `${api.url}/tasks/${task.id}/attachments/`,
    {
      headers: api.headers,
      multipart: {
        file: {
          name: "receipts-2025.pdf",
          mimeType: "application/pdf",
          buffer: Buffer.from("%PDF-1.4"),
        },
      },
    },
  )
  expect(uploaded.ok()).toBe(true)

  await page.goto(`/tasks?task=${task.id}`)
  const panel = page.getByRole("dialog", { name: "File the taxes" })
  await panel.getByRole("tab", { name: "Files" }).click()
  await expect(panel.getByText("receipts-2025.pdf")).toBeVisible()
  return { api, task, panel }
}

test("Deleting an attachment asks first, and names the file", async ({
  page,
}) => {
  const { api, task, panel } = await openFiles(page)

  // Download and delete are set well apart at desktop width too.
  const download = await panel
    .getByRole("button", { name: "Download receipts-2025.pdf" })
    .boundingBox()
  const trash = await panel
    .getByRole("button", { name: "Delete receipts-2025.pdf" })
    .boundingBox()
  if (!download || !trash) throw new Error("controls not on screen")
  expect(trash.x - (download.x + download.width)).toBeGreaterThanOrEqual(24)

  await panel.getByRole("button", { name: "Delete receipts-2025.pdf" }).click()
  const confirm = page.getByRole("dialog", {
    name: "Delete receipts-2025.pdf?",
  })
  await expect(confirm).toContainText("cannot be restored")

  // Cancelling leaves the file where it was.
  await confirm.getByRole("button", { name: "Cancel" }).click()
  await expect(confirm).toBeHidden()
  await expect(panel.getByText("receipts-2025.pdf")).toBeVisible()
  const kept = await (await api.get(`/tasks/${task.id}/attachments/`)).json()
  expect(kept.count).toBe(1)

  // Confirming removes it, and the list says so without a reload.
  await panel.getByRole("button", { name: "Delete receipts-2025.pdf" }).click()
  await confirm.getByRole("button", { name: "Delete file" }).click()
  await expect(confirm).toBeHidden()
  await expect(panel.getByText("receipts-2025.pdf")).toHaveCount(0)
  await expect(panel.getByText("No attachments yet.")).toBeVisible()
  const gone = await (await api.get(`/tasks/${task.id}/attachments/`)).json()
  expect(gone.count).toBe(0)
})

test("A failed deletion leaves the attachment and says what failed", async ({
  page,
}) => {
  const { panel } = await openFiles(page)
  await page.route("**/api/v1/attachments/*", (route) =>
    route.request().method() === "DELETE"
      ? route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Storage is unavailable" }),
        })
      : route.fallback(),
  )

  await panel.getByRole("button", { name: "Delete receipts-2025.pdf" }).click()
  const confirm = page.getByRole("dialog", {
    name: "Delete receipts-2025.pdf?",
  })
  await confirm.getByRole("button", { name: "Delete file" }).click()

  // The confirmation stays open for another try, and the file stays put.
  await expect(page.getByText("Storage is unavailable")).toBeVisible()
  await expect(confirm).toBeVisible()
  await confirm.getByRole("button", { name: "Cancel" }).click()
  await expect(panel.getByText("receipts-2025.pdf")).toBeVisible()
})

test.describe("on a touch screen", () => {
  test.use({
    viewport: { width: 320, height: 640 },
    hasTouch: true,
    isMobile: true,
  })

  test("Download and delete are thumb-sized and well apart", async ({
    page,
  }) => {
    const { panel } = await openFiles(page)
    const download = await panel
      .getByRole("button", { name: "Download receipts-2025.pdf" })
      .boundingBox()
    const remove = await panel
      .getByRole("button", { name: "Delete receipts-2025.pdf" })
      .boundingBox()
    if (!download || !remove) throw new Error("controls not on screen")

    for (const control of [download, remove]) {
      expect(control.width).toBeGreaterThanOrEqual(44)
      expect(control.height).toBeGreaterThanOrEqual(44)
    }
    // Side by side on one row, with clear space between them.
    expect(remove.x - (download.x + download.width)).toBeGreaterThanOrEqual(24)
    // And both still inside the panel at the narrowest width.
    const sheet = await panel.boundingBox()
    if (!sheet) throw new Error("panel not on screen")
    expect(remove.x + remove.width).toBeLessThanOrEqual(sheet.x + sheet.width)
  })
})
