import { expect, type Page, test } from "@playwright/test"
import { botColumn, botLine, openBot } from "./utils/bots"
import { randomEmail } from "./utils/random"
import { logInUser } from "./utils/user"

test.use({ storageState: { cookies: [], origins: [] } })

/** A user of this test's own: the suite shares a database with development. */
async function newUser(page: Page) {
  const email = randomEmail()
  await logInUser(page, email)
}

async function api(page: Page) {
  const token = await page.evaluate(() => localStorage.getItem("access_token"))
  return {
    url: `${process.env.VITE_API_URL}/api/v1`,
    headers: { Authorization: `Bearer ${token}` },
  }
}

/** A bot user with a project in its scope and, unless asked otherwise, a token. */
async function setUpBot(
  page: Page,
  { name = "Triage agent", withToken = true } = {},
) {
  const { url, headers } = await api(page)
  const project = await (
    await page.request.post(`${url}/projects/`, {
      headers,
      data: { name: "Support queue" },
    })
  ).json()
  const bot = await (
    await page.request.post(`${url}/bot-users/`, {
      headers,
      data: {
        name,
        scope: {
          project_ids: [project.id],
          permissions: {
            read_tasks: true,
            create_tasks: true,
            update_tasks: true,
            add_comments: true,
          },
        },
      },
    })
  ).json()
  let asBot: Record<string, string> = {}
  if (withToken) {
    const issued = await (
      await page.request.post(`${url}/bot-users/${bot.id}/token`, { headers })
    ).json()
    asBot = { Authorization: `Bearer ${issued.token}` }
  }
  return { url, headers, project, bot, asBot }
}

test("A bot user's column shows what that bot did, and not what the user did", async ({
  page,
}) => {
  await newUser(page)
  const { url, headers, project, asBot } = await setUpBot(page)

  // The bot works, and so does the user: only one of them is this feed.
  const created = await page.request.post(`${url}/tasks/`, {
    headers: asBot,
    data: { title: "Answer the refund request", project_id: project.id },
  })
  expect(created.ok()).toBe(true)
  await page.request.post(`${url}/tasks/`, {
    headers,
    data: { title: "Something I did myself", project_id: project.id },
  })

  await page.goto("/bots")
  await openBot(page, "Triage agent")
  const panel = botColumn(page, "Triage agent")

  const feed = panel.getByRole("list", {
    name: "Recent activity by Triage agent",
  })
  await expect(feed).toContainText("Answer the refund request")
  await expect(feed).not.toContainText("Something I did myself")
  // By the day, and with a way to the whole log.
  await expect(feed).toContainText("Today")
  await expect(
    panel
      .getByRole("region", { name: "Activity" })
      .getByRole("link", { name: /Everything it did/ }),
  ).toBeVisible()
})

test("A bot user's column lists the tasks it is on, and opens them", async ({
  page,
}) => {
  await newUser(page)
  const { url, headers, project, bot } = await setUpBot(page)
  await page.request.post(`${url}/tasks/`, {
    headers,
    data: {
      title: "Escalate the outage",
      project_id: project.id,
      assignee_id: bot.id,
    },
  })

  await page.goto("/bots")
  await openBot(page, "Triage agent")
  const panel = botColumn(page, "Triage agent")

  // No tabs: the tasks are a section of the one document, with their count.
  await expect(panel.getByRole("tab")).toHaveCount(0)
  await expect(
    panel.getByRole("region", { name: "On its plate" }),
  ).toContainText("1")
  const assigned = panel.getByRole("list", {
    name: "Tasks assigned to Triage agent",
  })
  await expect(assigned).toContainText("Escalate the outage")

  // Opening one swaps the column to the task; the bot user's own address is
  // one Back away.
  await assigned.getByRole("link", { name: "Escalate the outage" }).click()
  await expect(
    page.getByRole("complementary", { name: "Escalate the outage" }),
  ).toBeVisible()
  await page.goBack()
  await expect(botColumn(page, "Triage agent")).toBeVisible()
})

test("A bot user that has done nothing says what would appear", async ({
  page,
}) => {
  await newUser(page)
  await setUpBot(page, { name: "Quiet agent" })

  await page.goto("/bots")
  await openBot(page, "Quiet agent")
  const panel = botColumn(page, "Quiet agent")

  await expect(panel).toContainText("Every change this bot user makes")
  await expect(panel).toContainText(
    "No open tasks are assigned to this bot user",
  )
})

test("Token health is stated in words, not in timestamps", async ({ page }) => {
  await newUser(page)
  await setUpBot(page, { name: "Unused agent" })
  await setUpBot(page, { name: "Tokenless agent", withToken: false })

  await page.goto("/bots")
  await expect(botLine(page, "Unused agent")).toContainText("Working")
  await expect(botLine(page, "Unused agent")).toContainText("never used")
  await expect(botLine(page, "Tokenless agent")).toContainText("No token")
  await expect(botLine(page, "Tokenless agent")).toContainText("never used")

  await openBot(page, "Tokenless agent")
  const tokenless = botColumn(page, "Tokenless agent")
  await expect(tokenless).toContainText("No token")
  await expect(tokenless).toContainText("it cannot reach the API")
  await expect(
    tokenless.getByRole("button", { name: "Issue token" }),
  ).toBeVisible()
  await page.keyboard.press("Escape")

  await openBot(page, "Unused agent")
  const unused = botColumn(page, "Unused agent")
  await expect(unused).toContainText("Working")
  await expect(unused).toContainText("Never used")
})

test("An activity entry opens the bot user that made it, and the section hands off", async ({
  page,
}) => {
  await newUser(page)
  const { url, project, asBot } = await setUpBot(page)
  for (let index = 0; index < 7; index++) {
    await page.request.post(`${url}/tasks/`, {
      headers: asBot,
      data: { title: `Triaged ticket ${index}`, project_id: project.id },
    })
  }

  // From an unexpected change in the log to the integration responsible.
  await page.goto("/activity")
  await page
    .getByRole("listitem")
    .filter({ hasText: "Triaged ticket 6" })
    .getByRole("link", { name: "Triage agent" })
    .click()
  await expect(page).toHaveURL(/\/activity\?.*bot=/)
  const panel = botColumn(page, "Triage agent")
  await expect(panel).toBeVisible()

  // The preview is bounded, counts what is behind it, and says where the
  // rest is.
  await expect(
    panel
      .getByRole("list", { name: "Recent activity by Triage agent" })
      .locator("time"),
  ).toHaveCount(5)
  await expect(panel.getByRole("region", { name: "Activity" })).toContainText(
    "7",
  )
  await panel.getByRole("link", { name: /Everything it did/ }).click()

  await expect(page).toHaveURL(/actor=/)
  // The narrowing is said on the filter row, in ink, where it can be dropped.
  await expect(
    page.getByRole("button", { name: "Actor: By Triage agent" }),
  ).toBeVisible()
  await expect(
    page.getByRole("listitem").filter({ hasText: "Triaged ticket 0" }),
  ).toBeVisible()
})

test("The tasks on its plate hand off to the task list filtered to the bot", async ({
  page,
}) => {
  await newUser(page)
  const { url, headers, project, bot } = await setUpBot(page)
  for (let index = 0; index < 6; index++) {
    await page.request.post(`${url}/tasks/`, {
      headers,
      data: {
        title: `Assigned ${index}`,
        project_id: project.id,
        assignee_id: bot.id,
      },
    })
  }

  await page.goto("/bots")
  await openBot(page, "Triage agent")
  const panel = botColumn(page, "Triage agent")
  await expect(
    panel.getByRole("region", { name: "On its plate" }),
  ).toContainText("6")
  await panel.getByRole("link", { name: /All its tasks/ }).click()

  await expect(page).toHaveURL(new RegExp(`assignee=${bot.id}`))
  await expect(
    page.getByRole("link", { name: "Assigned 0", exact: true }),
  ).toBeVisible()
})
