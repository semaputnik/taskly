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

const openBot = (page: Page, name: string) =>
  page.getByRole("row", { name: `Open ${name}` }).click()

test("A bot user's panel shows what that bot did, and not what the user did", async ({
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
  const panel = page.getByRole("dialog", { name: "Triage agent" })

  const feed = panel.getByRole("list", {
    name: "Recent activity by Triage agent",
  })
  await expect(feed).toContainText("Answer the refund request")
  await expect(feed).not.toContainText("Something I did myself")
})

test("A bot user's panel lists the tasks it is on, and opens them", async ({
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
  const panel = page.getByRole("dialog", { name: "Triage agent" })
  await panel.getByRole("tab", { name: "Tasks" }).click()

  const assigned = panel.getByRole("list", {
    name: "Tasks assigned to Triage agent",
  })
  await expect(assigned).toContainText("Escalate the outage")

  // Opening one swaps the panel to the task; the bot user's own address is
  // one Back away.
  await assigned.getByRole("button", { name: "Escalate the outage" }).click()
  await expect(
    page.getByRole("dialog", { name: "Escalate the outage" }),
  ).toBeVisible()
  await page.goBack()
  await expect(page.getByRole("dialog", { name: "Triage agent" })).toBeVisible()
})

test("A bot user that has done nothing says what would appear", async ({
  page,
}) => {
  await newUser(page)
  await setUpBot(page, { name: "Quiet agent" })

  await page.goto("/bots")
  await openBot(page, "Quiet agent")
  const panel = page.getByRole("dialog", { name: "Quiet agent" })

  await expect(panel).toContainText("Every change this bot user makes")
  await panel.getByRole("tab", { name: "Tasks" }).click()
  await expect(panel).toContainText("No tasks are assigned to this bot user")
})

test("Token health is stated in words, not in timestamps", async ({ page }) => {
  await newUser(page)
  await setUpBot(page, { name: "Unused agent" })
  await setUpBot(page, { name: "Tokenless agent", withToken: false })

  await page.goto("/bots")
  // The last cell is the liveness column: the Token column beside it would
  // satisfy a looser assertion without the new column rendering at all.
  const liveness = (name: string) =>
    page
      .getByRole("row", { name: `Open ${name}` })
      .getByRole("cell")
      .last()
  await expect(liveness("Unused agent")).toHaveText("Never used")
  await expect(liveness("Tokenless agent")).toHaveText("Never used · no token")

  await openBot(page, "Tokenless agent")
  const tokenless = page.getByRole("dialog", { name: "Tokenless agent" })
  await expect(tokenless).toContainText(
    "No token — this bot user cannot reach the API",
  )
  await expect(
    tokenless.getByRole("button", { name: "Issue token" }),
  ).toBeVisible()
  await page.keyboard.press("Escape")

  await openBot(page, "Unused agent")
  const unused = page.getByRole("dialog", { name: "Unused agent" })
  await expect(unused).toContainText("Working")
  await expect(unused).toContainText("Never used")
})

test("An activity entry opens the bot user that made it, and the feed hands off", async ({
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
    .getByRole("row")
    .filter({ hasText: "Triaged ticket 6" })
    .getByRole("link", { name: "Triage agent" })
    .click()
  await expect(page).toHaveURL(/\/activity\?.*bot=/)
  const panel = page.getByRole("dialog", { name: "Triage agent" })
  await expect(panel).toBeVisible()

  // The preview is bounded, and says where the rest is.
  await expect(
    panel.getByText(/more entries in the activity log/),
  ).toBeVisible()
  await panel.getByText(/more entries in the activity log/).click()

  await expect(page).toHaveURL(/actor=/)
  await expect(page.getByText("Showing only")).toContainText("Triage agent")
  await expect(
    page.getByRole("row").filter({ hasText: "Triaged ticket 0" }),
  ).toBeVisible()
})

test("The assigned tasks hand off to the task list filtered to the bot", async ({
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
  const panel = page.getByRole("dialog", { name: "Triage agent" })
  await panel.getByRole("tab", { name: "Tasks" }).click()
  await panel
    .getByText(/more task in the task list|more tasks in the task list/)
    .click()

  await expect(page).toHaveURL(new RegExp(`assignee=${bot.id}`))
  await expect(page.getByRole("row", { name: /Assigned 0/ })).toBeVisible()
})

test("A deleted bot user still reads, and says it is gone", async ({
  page,
}) => {
  await newUser(page)
  const { url, headers, project, bot, asBot } = await setUpBot(page, {
    name: "Retired agent",
  })
  await page.request.post(`${url}/tasks/`, {
    headers: asBot,
    data: { title: "Its last act", project_id: project.id },
  })
  expect(
    (await page.request.delete(`${url}/bot-users/${bot.id}`, { headers })).ok(),
  ).toBe(true)

  // Gone from the list, and still readable at its own address.
  await page.goto("/bots")
  await expect(
    page.getByRole("row", { name: "Open Retired agent" }),
  ).toHaveCount(0)

  await page.goto(`/bots?bot=${bot.id}`)
  const panel = page.getByRole("dialog", { name: "Retired agent" })
  await expect(panel).toContainText("This bot user was deleted")
  await expect(panel).toContainText("cannot be undone")
  await expect(
    panel.getByRole("list", { name: "Recent activity by Retired agent" }),
  ).toContainText("Its last act")
  // Nothing about it changes again.
  await expect(panel.getByRole("textbox", { name: "Bot name" })).toHaveCount(0)
  await expect(
    panel.getByRole("button", { name: "Delete bot user" }),
  ).toHaveCount(0)
})
