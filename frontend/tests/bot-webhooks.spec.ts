import { expect, type Page, test } from "@playwright/test"
import { newUser, userApi } from "./utils/account"
import { botColumn, botLine } from "./utils/bots"
import { storeTokenAndClose } from "./utils/tokenDialog"
import { signedWith, startReceiver } from "./utils/webhookReceiver"

test.use({ storageState: { cookies: [], origins: [] } })

const hooks = (page: Page, bot: string) =>
  botColumn(page, bot).getByRole("region", { name: "Webhooks", exact: true })

const taskRow = (page: Page, bot: string) =>
  hooks(page, bot).getByRole("region", { name: "Task ready webhook" })

const commentRow = (page: Page, bot: string) =>
  hooks(page, bot).getByRole("region", { name: "Comment webhook" })

/** A bot user of the test's own, opened in its column. */
async function openNewBot(page: Page, name: string) {
  await newUser(page)
  const api = await userApi(page)
  const bot = await api.create("/bot-users/", {
    name,
    scope: { project_ids: [], permissions: {} },
  })
  await page.goto(`/bots?bot=${bot.id}`)
  await expect(botColumn(page, name)).toBeVisible()
  return { api, bot }
}

/** Set a webhook the way the owner's own client would. */
async function setWebhookByApi(
  page: Page,
  api: Awaited<ReturnType<typeof userApi>>,
  botId: string,
  kind: "task" | "comment",
  url: string,
) {
  const response = await page.request.put(
    `${api.url}/bot-users/${botId}/webhooks/${kind}`,
    { headers: api.headers, data: { url } },
  )
  expect(response.ok()).toBe(true)
  return (await response.json()) as { secret: string | null }
}

test("A URL is set, the secret shown once, a test sent and its result read", async ({
  page,
}) => {
  const receiver = await startReceiver()
  try {
    await openNewBot(page, "Triage agent")
    const row = taskRow(page, "Triage agent")

    // Nothing is set, and the empty row says what that means.
    await expect(row).toContainText("Not set")
    await expect(row).toContainText("not told about tasks")
    await expect(commentRow(page, "Triage agent")).toContainText("Not set")
    await expect(
      hooks(page, "Triage agent").getByRole("button", {
        name: "Regenerate secret",
      }),
    ).toHaveCount(0)
    await expect(botLine(page, "Triage agent")).not.toContainText("webhook")

    await row.getByRole("button", { name: "Set a URL" }).click()
    await row
      .getByRole("textbox", { name: "Task ready URL" })
      .fill(receiver.url())
    await row.getByRole("button", { name: "Save" }).click()

    // The first URL makes the secret, which is shown once and holds against
    // being dismissed by accident.
    const dialog = page.getByRole("dialog", {
      name: "Webhook secret for Triage agent",
    })
    await expect(dialog).toBeVisible()
    await page.keyboard.press("Escape")
    await expect(dialog).toBeVisible()
    const secret = await dialog
      .getByRole("textbox", { name: "Webhook secret" })
      .inputValue()
    expect(secret).toBeTruthy()
    await storeTokenAndClose(dialog, "secret")

    await expect(row).toContainText(receiver.url())
    await expect(row).toContainText("No delivery yet")
    await expect(botLine(page, "Triage agent")).toContainText(
      "task webhook set",
    )

    // A test is sent at once, and what came of it is the last delivery.
    await row.getByRole("button", { name: "Send a test" }).click()
    await expect(row).toContainText("Delivered")
    await expect(row).toContainText("test")
    await expect(row).toContainText("200")
    expect(receiver.received).toHaveLength(1)
    const [delivery] = receiver.received
    expect(delivery.headers["x-taskly-event"]).toBe("test")
    // The secret on screen is the one that signs.
    expect(signedWith(secret, delivery)).toBe(true)
    await expect(botLine(page, "Triage agent")).not.toContainText(
      "last delivery failed",
    )

    // A receiver that refuses makes the last delivery a failure, in red, on
    // the line as well.
    receiver.answerWith(500)
    await row.getByRole("button", { name: "Send a test" }).click()
    await expect(row).toContainText("Failed")
    await expect(row).toContainText("500")
    const failed = botLine(page, "Triage agent").getByText(
      "last delivery failed",
    )
    await expect(failed).toBeVisible()
    await expect(failed).toHaveClass(/text-late/)

    // The record is the server's: it is the same after a reload.
    await page.reload()
    await expect(taskRow(page, "Triage agent")).toContainText("Failed")
    await expect(taskRow(page, "Triage agent")).toContainText(receiver.url())
  } finally {
    await receiver.close()
  }
})

test("An address the server refuses is answered in the field", async ({
  page,
}) => {
  await openNewBot(page, "Triage agent")
  const row = commentRow(page, "Triage agent")

  await row.getByRole("button", { name: "Set a URL" }).click()
  const field = row.getByRole("textbox", { name: "Comment URL" })
  await field.fill("ftp://hooks.example.test/inbox")
  await row.getByRole("button", { name: "Save" }).click()

  const refusal = row.getByRole("alert")
  await expect(refusal).toContainText(/http/i)
  await expect(field).toHaveAttribute("aria-invalid", "true")
  // What was typed is kept for correcting, and nothing was made.
  await expect(field).toHaveValue("ftp://hooks.example.test/inbox")
  await expect(page.getByRole("dialog")).toHaveCount(0)

  // Typing again takes the refusal away; Escape forgets the edit and leaves
  // the column open.
  await field.fill("https://hooks.example.test/inbox")
  await expect(refusal).toBeHidden()
  await field.press("Escape")
  await expect(field).toBeHidden()
  await expect(row).toContainText("Not set")
  await expect(botColumn(page, "Triage agent")).toBeVisible()
})

test("A URL is changed, and cleared once its loss is confirmed", async ({
  page,
}) => {
  const receiver = await startReceiver()
  try {
    const { api, bot } = await openNewBot(page, "Triage agent")
    await setWebhookByApi(page, api, bot.id, "task", receiver.url("/first"))
    await setWebhookByApi(page, api, bot.id, "comment", receiver.url("/second"))
    await page.reload()
    const row = taskRow(page, "Triage agent")
    await expect(row).toContainText("/first")
    await expect(botLine(page, "Triage agent")).toContainText(
      "both webhooks set",
    )

    await row.getByRole("button", { name: "Change" }).click()
    const field = row.getByRole("textbox", { name: "Task ready URL" })
    await expect(field).toHaveValue(receiver.url("/first"))
    await field.fill(receiver.url("/changed"))
    await field.press("Enter")
    await expect(row).toContainText("/changed")
    // Changing a URL does not make a second secret to show.
    await expect(page.getByRole("dialog")).toHaveCount(0)

    // Clearing says what goes with it, and the other webhook stays.
    await row.getByRole("button", { name: "Clear" }).click()
    const confirm = page.getByRole("dialog", {
      name: "Clear the task ready webhook of Triage agent?",
    })
    await expect(confirm).toContainText("The other webhook and the secret stay")
    await confirm.getByRole("button", { name: "Clear webhook" }).click()
    await expect(row).toContainText("Not set")
    await expect(botLine(page, "Triage agent")).toContainText(
      "comment webhook set",
    )

    // The last one takes the secret with it, and says so beforehand.
    const comment = commentRow(page, "Triage agent")
    await comment.getByRole("button", { name: "Clear" }).click()
    const last = page.getByRole("dialog", {
      name: "Clear the comment webhook of Triage agent?",
    })
    await expect(last).toContainText("the secret is discarded too")
    await last.getByRole("button", { name: "Clear webhook" }).click()
    await expect(comment).toContainText("Not set")
    await expect(
      hooks(page, "Triage agent").getByRole("button", {
        name: "Regenerate secret",
      }),
    ).toHaveCount(0)

    // So the next URL makes a new one, shown once.
    await row.getByRole("button", { name: "Set a URL" }).click()
    await row
      .getByRole("textbox", { name: "Task ready URL" })
      .fill(receiver.url("/again"))
    await row.getByRole("button", { name: "Save" }).click()
    await storeTokenAndClose(
      page.getByRole("dialog", { name: "Webhook secret for Triage agent" }),
      "secret",
    )
  } finally {
    await receiver.close()
  }
})

test("The secret is regenerated, shown once, and signs from then on", async ({
  page,
}) => {
  const receiver = await startReceiver()
  try {
    const { api, bot } = await openNewBot(page, "Triage agent")
    const first = (
      await setWebhookByApi(page, api, bot.id, "task", receiver.url())
    ).secret
    expect(first).toBeTruthy()
    await page.reload()

    await hooks(page, "Triage agent")
      .getByRole("button", { name: "Regenerate secret" })
      .click()
    const confirm = page.getByRole("dialog", {
      name: "Regenerate the webhook secret of Triage agent?",
    })
    await confirm.getByRole("button", { name: "Cancel" }).click()
    await expect(confirm).toBeHidden()

    await hooks(page, "Triage agent")
      .getByRole("button", { name: "Regenerate secret" })
      .click()
    await confirm.getByRole("button", { name: "Regenerate" }).click()

    const dialog = page.getByRole("dialog", {
      name: "Webhook secret for Triage agent",
    })
    await expect(dialog).toBeVisible()
    const second = await dialog
      .getByRole("textbox", { name: "Webhook secret" })
      .inputValue()
    expect(second).not.toBe(first)
    await storeTokenAndClose(dialog, "secret")

    await taskRow(page, "Triage agent")
      .getByRole("button", { name: "Send a test" })
      .click()
    await expect(taskRow(page, "Triage agent")).toContainText("Delivered")
    const [delivery] = receiver.received
    expect(signedWith(second, delivery)).toBe(true)
    expect(signedWith(first ?? "", delivery)).toBe(false)
  } finally {
    await receiver.close()
  }
})

test("A deleted bot user shows its webhooks, and none can be changed", async ({
  page,
}) => {
  const { api, bot } = await openNewBot(page, "Retired agent")
  await setWebhookByApi(
    page,
    api,
    bot.id,
    "task",
    "https://hooks.example.test/x",
  )
  const deleted = await page.request.delete(`${api.url}/bot-users/${bot.id}`, {
    headers: api.headers,
  })
  expect(deleted.ok()).toBe(true)

  await page.goto(`/bots?bot=${bot.id}`)
  const section = hooks(page, "Retired agent")
  await expect(section).toBeVisible()
  await expect(section).toContainText("cleared when this bot user was deleted")
  await expect(taskRow(page, "Retired agent")).toContainText("Not set")
  await expect(section.getByRole("button")).toHaveCount(0)
})

test.describe("on a phone", () => {
  test.use({
    viewport: { width: 375, height: 812 },
    hasTouch: true,
    isMobile: true,
  })

  test("The section fits the screen and its controls are thumb-sized", async ({
    page,
  }) => {
    const { api, bot } = await openNewBot(page, "Triage agent")
    await setWebhookByApi(
      page,
      api,
      bot.id,
      "task",
      "https://hooks.example.test/a/very/long/path/that/would/overflow/a/phone/screen/if/it/could",
    )
    await page.reload()

    const section = hooks(page, "Triage agent")
    await section.scrollIntoViewIfNeeded()
    await expect(taskRow(page, "Triage agent")).toContainText("hooks.example")

    // Nothing pushes the page sideways.
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    )
    expect(overflow).toBeLessThanOrEqual(0)

    for (const name of [
      "Send a test",
      "Change",
      "Clear",
      "Regenerate secret",
    ]) {
      const box = await section
        .getByRole("button", { name, exact: true })
        .boundingBox()
      expect(box?.height).toBeGreaterThanOrEqual(44)
    }
  })
})
