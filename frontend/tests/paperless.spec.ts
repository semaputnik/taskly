import { readFile } from "node:fs/promises"
import { expect, type Page, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"
import { startPaperlessStub } from "./utils/paperlessStub"

test.use({ storageState: { cookies: [], origins: [] } })

// A hand-over runs in the API's background loop, which looks again every ten
// seconds, so a PDF reaches Paperless some seconds after it is attached.
const HANDOVER = { timeout: 60_000 }

const section = (page: Page) =>
  page.getByRole("region", { name: "Paperless", exact: true })

/** Connect the way the owner does: the address and the token, in the section. */
async function connect(page: Page, stub: { url: string; token: string }) {
  await page.goto("/settings")
  const paperless = section(page)
  await expect(paperless).toContainText("Not connected")
  await paperless.getByRole("button", { name: "Connect Paperless" }).click()
  await paperless.getByLabel("Address", { exact: true }).fill(stub.url)
  await paperless.getByLabel("Token", { exact: true }).fill(stub.token)
  await paperless.getByRole("button", { name: "Connect", exact: true }).click()
  await expect(paperless).toContainText("Connected")
  return paperless
}

test("Paperless is connected, a PDF is kept there, and disconnecting says what it puts out of reach", async ({
  page,
}) => {
  test.setTimeout(150_000)
  const stub = await startPaperlessStub()
  try {
    await newUser(page)
    const api = await userApi(page)
    const task = await api.create("/tasks/", { title: "File the taxes" })

    // Nothing is connected, and the section says what connecting does.
    await page.goto("/settings")
    const paperless = section(page)
    await expect(paperless).toContainText("Not connected")
    await expect(paperless).toContainText("kept there")
    await expect(
      paperless.getByText("Kept there", { exact: true }),
    ).toHaveCount(0)

    await connect(page, stub)
    await expect(paperless).toContainText(stub.url)
    // The token is kept and never shown, only replaced.
    await expect(paperless).toContainText("set, never shown again")
    await expect(paperless).toContainText("No PDFs yet")
    await expect(page.getByText(stub.token)).toHaveCount(0)

    // Test says how it went, in words.
    await paperless.getByRole("button", { name: "Test" }).click()
    await expect(paperless).toContainText(
      "Paperless answered and accepted the token.",
    )

    // Attaching a PDF: it is here at once, then on its way, then kept there,
    // with no reload in between.
    await page.goto(`/tasks?task=${task.id}`)
    const panel = page.getByRole("complementary", { name: "File the taxes" })
    const files = panel.getByRole("region", { name: "Files" })
    const pdf = Buffer.from(`%PDF-1.4 ${Date.now()}`)
    await files.locator('input[type="file"]').setInputFiles({
      name: "receipts-2025.pdf",
      mimeType: "application/pdf",
      buffer: pdf,
    })
    await expect(files).toContainText("sending to Paperless…")
    // Downloadable from the moment it is accepted (FR-04.6).
    const early = page.waitForEvent("download")
    await files
      .getByRole("button", { name: "Download receipts-2025.pdf" })
      .click()
    expect((await early).suggestedFilename()).toBe("receipts-2025.pdf")

    const link = files.getByRole("link", { name: /kept in Paperless/ })
    await expect(link).toBeVisible(HANDOVER)
    await expect(link).toHaveAttribute(
      "href",
      `${stub.url}/documents/1/details`,
    )
    await expect(files).not.toContainText("sending to Paperless")

    // What Paperless was given: the file, its name, the tag and a note.
    expect(stub.documents).toHaveLength(1)
    const [document] = stub.documents
    expect(document.title).toBe("receipts-2025.pdf")
    expect(document.bytes.equals(pdf)).toBe(true)
    expect(document.tags).toContain(stub.tags[0].id)
    expect(stub.tags[0].name).toBe("Taskly")
    expect(document.notes).toHaveLength(1)
    expect(document.notes[0]).toContain(`/tasks?task=${task.id}`)

    // The download now comes from Paperless, as the original file.
    const downloading = page.waitForEvent("download")
    await files
      .getByRole("button", { name: "Download receipts-2025.pdf" })
      .click()
    const path = await (await downloading).path()
    expect((await readFile(path)).equals(pdf)).toBe(true)

    // Removing it asks, and says Paperless keeps the document.
    await files
      .getByRole("button", { name: "Remove receipts-2025.pdf" })
      .click()
    const removal = page.getByRole("dialog", {
      name: "Delete receipts-2025.pdf?",
    })
    await expect(removal).toContainText("stays in Paperless")
    await removal.getByRole("button", { name: "Cancel" }).click()

    // The section counts what is kept there.
    await page.goto("/settings")
    await expect(paperless).toContainText("1 PDF")

    // Disconnecting says how many PDFs are put out of reach, before it asks.
    await paperless.getByRole("button", { name: "Disconnect" }).click()
    const confirm = page.getByRole("dialog", { name: "Disconnect Paperless?" })
    await expect(confirm).toContainText("1 PDF kept in Paperless")
    await expect(confirm).toContainText("nothing is deleted from it")
    await confirm.getByRole("button", { name: "Cancel" }).click()
    await expect(paperless).toContainText("Connected")

    await paperless.getByRole("button", { name: "Disconnect" }).click()
    await confirm.getByRole("button", { name: "Disconnect" }).click()
    await expect(confirm).toBeHidden()
    await expect(paperless).toContainText("Not connected")
    await expect(paperless).toContainText("out of reach until Paperless")
    await expect(page.getByText("1 PDF out of reach")).toBeVisible()
    // Nothing was deleted in Paperless.
    expect(stub.documents).toHaveLength(1)

    // The file is out of reach, and says so, in words.
    await page.goto(`/tasks?task=${task.id}`)
    await expect(files).toContainText("kept in Paperless, not connected")
    await files
      .getByRole("button", { name: "Download receipts-2025.pdf" })
      .click()
    await expect(page.getByText("Paperless is not connected")).toBeVisible()
  } finally {
    await stub.close()
  }
})

test("The address is changed with its token, the token is replaced, and refusals are said in the field", async ({
  page,
}) => {
  const stub = await startPaperlessStub()
  const other = await startPaperlessStub("another-token")
  try {
    await newUser(page)
    const paperless = await connect(page, stub)

    // A refused address is said at the address, in the server's words.
    await paperless.getByRole("button", { name: "Change" }).click()
    const address = paperless.getByLabel("Address", { exact: true })
    await expect(address).toHaveValue(stub.url)
    await address.fill("ftp://paperless.example.com")
    await paperless.getByLabel("Token", { exact: true }).fill("x")
    await paperless.getByRole("button", { name: "Save" }).click()
    await expect(paperless.getByRole("alert")).toContainText("http")
    await expect(address).toHaveValue("ftp://paperless.example.com")

    // A new address asks for its token again: a stored one is never sent to
    // an address typed later.
    await address.fill(other.url)
    await paperless.getByLabel("Token", { exact: true }).fill("")
    await paperless.getByRole("button", { name: "Save" }).click()
    await expect(paperless.getByRole("alert")).toContainText(
      "Enter the API token for this address.",
    )

    // Test tries what is typed without saving it: a wrong token is a failed
    // test in words, and nothing was changed.
    await paperless.getByLabel("Token", { exact: true }).fill("not-the-token")
    await paperless.getByRole("button", { name: "Test" }).click()
    await expect(paperless).toContainText("Paperless refused the token")
    await paperless.getByRole("button", { name: "Cancel" }).click()
    await expect(paperless).toContainText(stub.url)

    // With the right one it is saved.
    await paperless.getByRole("button", { name: "Change" }).click()
    await paperless.getByLabel("Address", { exact: true }).fill(other.url)
    await paperless.getByLabel("Token", { exact: true }).fill(other.token)
    await paperless.getByRole("button", { name: "Save" }).click()
    await expect(paperless).toContainText(other.url)

    // The token is replaced on its own line; the address stays.
    await paperless.getByRole("button", { name: "Replace" }).click()
    await paperless.getByLabel("Token", { exact: true }).fill("wrong-token")
    await paperless.getByRole("button", { name: "Save" }).click()
    await expect(paperless).toContainText("set, never shown again")
    await expect(paperless).toContainText(other.url)
    // Saved without trying it, so the next test says the token is refused.
    await paperless.getByRole("button", { name: "Test" }).click()
    await expect(paperless).toContainText("Paperless refused the token")

    await paperless.getByRole("button", { name: "Replace" }).click()
    await paperless.getByLabel("Token", { exact: true }).fill(other.token)
    await paperless.getByRole("button", { name: "Save" }).click()
    await paperless.getByRole("button", { name: "Test" }).click()
    await expect(paperless).toContainText(
      "Paperless answered and accepted the token.",
    )
  } finally {
    await stub.close()
    await other.close()
  }
})

test("A failed hand-over says why and can be sent again", async ({ page }) => {
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

  // Every attempt is spent only after hours, so the failure is the answer the
  // test hands the page.
  let resent = 0
  await page.route(`**/api/v1/tasks/${task.id}/attachments/`, async (route) => {
    const response = await route.fetch()
    const body = await response.json()
    body.data[0].paperless_handover =
      resent === 0
        ? {
            state: "failed",
            error: "Paperless refused the token (it answered 401)",
            attempts: 6,
            next_attempt_at: null,
          }
        : {
            state: "pending",
            error: null,
            attempts: 0,
            next_attempt_at: new Date().toISOString(),
          }
    await route.fulfill({ response, json: body })
  })
  await page.route("**/api/v1/attachments/*/resend", async (route) => {
    resent += 1
    await route.fulfill({ json: {} })
  })

  await page.goto(`/tasks?task=${task.id}`)
  const files = page
    .getByRole("complementary", { name: "File the taxes" })
    .getByRole("region", { name: "Files" })
  await expect(files).toContainText("kept here")
  await expect(files).toContainText(
    "Paperless would not take it: Paperless refused the token (it answered 401)",
  )

  await files
    .getByRole("button", { name: "Send receipts-2025.pdf again" })
    .click()
  await expect(files).toContainText("sending to Paperless…")
  await expect(files).not.toContainText("would not take it")
  expect(resent).toBe(1)
})
