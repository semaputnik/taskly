import { expect, type Page, test } from "@playwright/test"
import { isoDay } from "../src/lib/dates"
import { newUser, userApi } from "./utils/account"
import {
  chooseFilter,
  chooseOrder,
  lineTitles,
  taskLine,
  taskLines,
} from "./utils/tasks"

test.use({ storageState: { cookies: [], origins: [] } })

const DAY = 86_400_000
const daysFromNow = (days: number) => isoDay(new Date(Date.now() + days * DAY))

/** More tasks than one page holds, so paging has something to page. */
async function seedTasks(
  page: Page,
  count: number,
  extra: (index: number) => Record<string, unknown> = () => ({}),
) {
  const api = await userApi(page)
  const ids: string[] = []
  for (let index = 0; index < count; index++) {
    const created = await api.create("/tasks/", {
      title: `Task ${String(index).padStart(2, "0")}`,
      ...extra(index),
    })
    ids.push(created.id)
  }
  return ids
}

/** A bot user of the account's, scoped to the given projects. */
async function seedBot(
  page: Page,
  name: string,
  projectIds: string[],
): Promise<{ id: string }> {
  const api = await userApi(page)
  return api.create("/bot-users/", {
    name,
    scope: {
      project_ids: projectIds,
      permissions: { read_tasks: true, update_tasks: true },
    },
  })
}

const notice = (page: Page) => page.locator("[data-sonner-toast]")

test("The page says how much is open, in Backlog, on bot users and overdue", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const project = await api.create("/projects/", { name: "Releases" })
  const bot = await seedBot(page, "release-bot", [project.id])
  await api.create("/tasks/", { title: "Plain backlog" })
  await api.create("/tasks/", { title: "Another backlog" })
  await api.create("/tasks/", {
    title: "Late",
    status: "todo",
    due_date: daysFromNow(-3),
  })
  await api.create("/tasks/", {
    title: "On the bot",
    status: "in_progress",
    project_id: project.id,
    assignee_id: bot.id,
  })
  // Done work is not open, and does not count.
  await api.create("/tasks/", { title: "Finished", status: "done" })

  await page.goto("/tasks")
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Tasks")
  await expect(page.getByText("4 open.")).toBeVisible()
  await expect(
    page.getByText("2 in Backlog, 1 on bot users, 1 overdue."),
  ).toBeVisible()
})

test("The footer counts what matches, and every task is reachable by paging", async ({
  page,
}) => {
  await newUser(page)
  await seedTasks(page, 28)

  await page.goto("/tasks")
  await expect(page.getByText("28 tasks · page 1 of 2")).toBeVisible()
  // Newest filed first: the last task written leads the first page.
  await expect(lineTitles(page)).toHaveCount(25)
  await expect(taskLine(page, "Task 27")).toBeVisible()
  await expect(taskLine(page, "Task 02")).toHaveCount(0)
  await expect(page.getByRole("button", { name: "Previous" })).toBeDisabled()

  await page.getByRole("button", { name: "Next" }).click()
  await expect(page).toHaveURL(/page=2/)
  await expect(page.getByText("28 tasks · page 2 of 2")).toBeVisible()
  await expect(taskLine(page, "Task 02")).toBeVisible()
  await expect(lineTitles(page)).toHaveText(["Task 02", "Task 01", "Task 00"])
  await expect(page.getByRole("button", { name: "Next" })).toBeDisabled()

  // The page is part of the address, so a reload lands where it left off.
  await page.reload()
  await expect(taskLine(page, "Task 00")).toBeVisible()

  await page.getByRole("button", { name: "Previous" }).click()
  await expect(page).not.toHaveURL(/page=/)
  await expect(taskLine(page, "Task 27")).toBeVisible()
})

test("The list opens newest filed first with each subtask under its root, and a chosen order flattens it", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const older = await api.create("/tasks/", { title: "Older root" })
  await api.create("/tasks/", { title: "Newer root" })
  await api.create("/tasks/", { title: "Its subtask", parent_id: older.id })

  await page.goto("/tasks")
  // Newest filed first is by root: the subtask, though newest of all, sits
  // under the root it belongs to rather than at the top.
  await expect(lineTitles(page)).toHaveText([
    "Newer root",
    "Older root",
    "Its subtask",
  ])
  const subtask = taskLine(page, "Its subtask")
  await expect(subtask.getByRole("img", { name: "Subtask" })).toBeVisible()
  await expect(
    taskLine(page, "Older root").getByRole("img", { name: "Subtask" }),
  ).toHaveCount(0)
  // Indented under the root, not flush with it.
  const rootBox = await taskLine(page, "Older root")
    .getByRole("checkbox")
    .boundingBox()
  const subBox = await subtask.getByRole("checkbox").boundingBox()
  expect(subBox?.x ?? 0).toBeGreaterThan((rootBox?.x ?? 0) + 20)

  // An order of the reader's own puts every task at its own place.
  await chooseOrder(page, /^Filed/)
  await expect(page).toHaveURL(/sort=created_at/)
  await expect(lineTitles(page)).toHaveText([
    "Its subtask",
    "Newer root",
    "Older root",
  ])
  // Flat: the subtask is no longer drawn under a root, so it is flush with
  // the others and carries the plain glyph of a subtask on its own.
  const flat = await taskLine(page, "Its subtask")
    .getByRole("checkbox")
    .boundingBox()
  expect(flat?.x ?? 0).toBeCloseTo(rootBox?.x ?? 0, 0)
})

test("The order menu sorts the whole result set, and choosing an order again reverses it", async ({
  page,
}) => {
  await newUser(page)
  // Due dates run backwards against the titles, so the extreme value is only
  // on the first page if the server did the sorting.
  await seedTasks(page, 28, (index) => ({
    due_date: `2030-01-${String(28 - index).padStart(2, "0")}`,
  }))

  await page.goto("/tasks")
  await chooseOrder(page, "Due date")
  await expect(page).toHaveURL(/sort=due_date/)
  await expect(page).not.toHaveURL(/order=/)
  // The earliest due date belongs to the last task written.
  await expect(lineTitles(page).first()).toHaveText("Task 27")
  await expect(
    page.getByRole("button", { name: "Order: Due soonest first" }),
  ).toBeVisible()

  await page.getByRole("button", { name: "Order: Due soonest first" }).click()
  // The menu says what choosing it again does.
  await expect(
    page.getByRole("menuitemradio", { name: /^Due date/ }),
  ).toContainText("Choose again to reverse")
  await page.getByRole("menuitemradio", { name: /^Due date/ }).click()
  await expect(page.getByRole("menu")).toHaveCount(0)
  await expect(page).toHaveURL(/order=desc/)
  await expect(lineTitles(page).first()).toHaveText("Task 00")
  await expect(
    page.getByRole("button", { name: "Order: Due latest first" }),
  ).toBeVisible()

  // Chosen again it turns round once more.
  await chooseOrder(page, /^Due date/)
  await expect(page).not.toHaveURL(/order=/)
  await expect(lineTitles(page).first()).toHaveText("Task 27")

  // Priority and Filed are orders too, and the order survives a reload.
  await chooseOrder(page, /^Filed/)
  await chooseOrder(page, /^Filed/)
  await expect(page).toHaveURL(
    /sort=created_at&order=asc|order=asc&sort=created_at/,
  )
  await page.reload()
  await expect(
    page.getByRole("button", { name: "Order: Filed, oldest first" }),
  ).toBeVisible()
  await expect(lineTitles(page).first()).toHaveText("Task 00")

  // Back to the list's own order drops both from the address.
  await chooseOrder(page, "Newest first")
  await expect(page).not.toHaveURL(/sort=|order=/)
  await expect(lineTitles(page).first()).toHaveText("Task 27")

  await chooseOrder(page, /^Priority/)
  await expect(page).toHaveURL(/sort=priority/)
})

test("Changing a filter returns to the first page", async ({ page }) => {
  await newUser(page)
  const api = await userApi(page)
  const project = await api.create("/projects/", { name: "Sweep" })
  await seedTasks(page, 28)
  await api.create("/tasks/", {
    title: "In the project",
    project_id: project.id,
  })

  await page.goto("/tasks?page=2")
  await expect(page.getByText("page 2 of 2")).toBeVisible()

  await chooseFilter(page, "Any project", "Sweep")

  await expect(page).not.toHaveURL(/page=2/)
  await expect(taskLine(page, "In the project")).toBeVisible()
  await expect(lineTitles(page)).toHaveCount(1)
})

test("Filters narrow together, a set one reads in ink with an x, and Clear drops them all", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const me = await (await api.get("/users/me")).json()
  const project = await api.create("/projects/", { name: "Website" })
  const bot = await seedBot(page, "release-bot", [project.id])
  await api.create("/tags/", { name: "copy" })
  await api.create("/tasks/", {
    title: "Mine and urgent",
    project_id: project.id,
    assignee_id: me.id,
    priority: "P1",
    status: "todo",
    tags: ["copy"],
  })
  await api.create("/tasks/", {
    title: "Mine and idle",
    project_id: project.id,
    assignee_id: me.id,
    priority: "P4",
    status: "waiting",
  })
  await api.create("/tasks/", {
    title: "The bot's",
    project_id: project.id,
    assignee_id: bot.id,
    status: "review",
  })
  await api.create("/tasks/", { title: "Nobody's" })

  await page.goto("/tasks")
  await expect(lineTitles(page)).toHaveCount(4)

  // Quiet until set: every filter is a text button saying "Any ...".
  for (const name of [
    "Any project",
    "Anyone",
    "Any status",
    "Any priority",
    "Any tag",
    "Any time",
  ]) {
    await expect(page.getByRole("button", { name })).toBeVisible()
  }
  await expect(
    page.getByRole("button", { name: "Clear all filters" }),
  ).toHaveCount(0)

  await chooseFilter(page, "Any project", "Website")
  await expect(lineTitles(page)).toHaveCount(3)
  // Set: named for what it is, a weight up, with an x that drops it.
  const set = page.getByRole("button", { name: "Project: Website" })
  await expect(set).toHaveCSS("font-weight", "500")

  await chooseFilter(page, "Anyone", "Me")
  await expect(lineTitles(page)).toHaveText([
    "Mine and idle",
    "Mine and urgent",
  ])
  await chooseFilter(page, "Any priority", "P1")
  await expect(lineTitles(page)).toHaveText(["Mine and urgent"])
  await expect(page).toHaveURL(/priority=P1/)
  await expect(page).toHaveURL(/assignee=me/)

  // Each x drops its own filter and leaves the rest.
  await page.getByRole("button", { name: "Remove the priority filter" }).click()
  await expect(lineTitles(page)).toHaveCount(2)
  await chooseFilter(page, "Any status", "Waiting")
  await expect(lineTitles(page)).toHaveText(["Mine and idle"])
  await page.getByRole("button", { name: "Remove the status filter" }).click()

  await chooseFilter(page, "Assignee: Assigned to me", "release-bot")
  await expect(lineTitles(page)).toHaveText(["The bot's"])
  await chooseFilter(page, "Assignee: release-bot", "Unassigned")
  await expect(lineTitles(page)).toHaveCount(0)
  await expect(page.getByText("No tasks match these filters")).toBeVisible()

  await page.getByRole("button", { name: "Clear all filters" }).click()
  await expect(lineTitles(page)).toHaveCount(4)
  await expect(page).not.toHaveURL(/project_id|assignee|priority|status/)

  await chooseFilter(page, "Any tag", "copy")
  await expect(lineTitles(page)).toHaveText(["Mine and urgent"])
  await expect(page).toHaveURL(/tag=copy/)
  await page.reload()
  await expect(page.getByRole("button", { name: "Tag: copy" })).toBeVisible()
  await expect(lineTitles(page)).toHaveText(["Mine and urgent"])
})

test("The time filter takes overdue, or a range of due dates", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  await api.create("/tasks/", { title: "Late", due_date: daysFromNow(-4) })
  await api.create("/tasks/", { title: "Soon", due_date: daysFromNow(3) })
  await api.create("/tasks/", { title: "Far", due_date: daysFromNow(40) })
  await api.create("/tasks/", { title: "Whenever" })

  await page.goto("/tasks")
  await page.getByRole("button", { name: "Any time" }).click()
  await page.getByRole("checkbox", { name: "Overdue" }).click()
  await expect(page).toHaveURL(/overdue=true/)
  await expect(lineTitles(page)).toHaveText(["Late"])
  await page.keyboard.press("Escape")
  await expect(
    page.getByRole("button", { name: "Time: Overdue" }),
  ).toBeVisible()

  await page.getByRole("button", { name: "Remove the time filter" }).click()
  await expect(lineTitles(page)).toHaveCount(4)

  await page.getByRole("button", { name: "Any time" }).click()
  const dialog = page.getByRole("dialog")
  await dialog.locator('input[type="date"]').first().fill(daysFromNow(1))
  await dialog.locator('input[type="date"]').last().fill(daysFromNow(10))
  await expect(page).toHaveURL(/due_from=/)
  await expect(page).toHaveURL(/due_to=/)
  await expect(lineTitles(page)).toHaveText(["Soon"])
  await page.keyboard.press("Escape")

  await page.getByRole("button", { name: "Clear all filters" }).click()
  await expect(lineTitles(page)).toHaveCount(4)
})

test("The three empty states say three different things", async ({ page }) => {
  await newUser(page)
  const api = await userApi(page)

  // Nothing was ever written down.
  await page.goto("/tasks")
  await expect(page.getByText("No tasks yet")).toBeVisible()
  await expect(page.getByText("Nothing is open.")).toBeVisible()
  await expect(
    page.getByRole("link", { name: "Set up a bot user" }),
  ).toBeVisible()
  await expect(page.getByRole("button", { name: "Next" })).toHaveCount(0)

  // Everything written is done.
  await api.create("/tasks/", { title: "Done already", status: "done" })
  await page.reload()
  await expect(page.getByText("Nothing left open")).toBeVisible()
  await expect(page.getByText("No tasks yet")).toHaveCount(0)
  await page.getByRole("link", { name: "activity log" }).click()
  await expect(page).toHaveURL(/\/activity/)

  // Something is open, but the filters exclude it.
  await api.create("/tasks/", { title: "Open and plain" })
  await page.goto("/tasks")
  await chooseFilter(page, "Any priority", "P1")
  await expect(page.getByText("No tasks match these filters")).toBeVisible()
  await expect(page.getByText("Nothing left open")).toHaveCount(0)
  await page.getByRole("button", { name: "clear them all" }).click()
  await expect(taskLine(page, "Open and plain")).toBeVisible()
})

test("A task is closed from its line, which leaves the list with a notice", async ({
  page,
}) => {
  await newUser(page)
  await seedTasks(page, 1)

  await page.goto("/tasks")
  await taskLine(page, "Task 00")
    .getByRole("checkbox", { name: "Mark as done" })
    .click()
  // The list holds open work (ADR-0006), so the line goes and the notice
  // carries the way back.
  await expect(taskLine(page, "Task 00")).toHaveCount(0)
  const toast = notice(page).filter({ hasText: "Task 00" })
  await expect(toast).toBeVisible()
  await toast.getByRole("button", { name: "Undo" }).click()
  await expect(taskLine(page, "Task 00")).toBeVisible()
})

test("The list is lines alone: no table, view switch, selection or bulk bar, and an old view in the address is ignored", async ({
  page,
}) => {
  await newUser(page)
  await seedTasks(page, 3)

  await page.goto("/tasks?view=table")
  await expect(lineTitles(page)).toHaveCount(3)
  await expect(page.getByRole("table")).toHaveCount(0)
  await expect(page.getByRole("columnheader")).toHaveCount(0)
  await expect(page.getByRole("button", { name: "Compact" })).toHaveCount(0)
  await expect(page.getByRole("button", { name: "Table" })).toHaveCount(0)
  await expect(page.getByRole("button", { name: "Filters" })).toHaveCount(0)
  await expect(page.getByRole("checkbox", { name: /^Select/ })).toHaveCount(0)
  await expect(page.getByText("selected", { exact: false })).toHaveCount(0)
  // The only checkboxes are each line's own mark, which closes the task.
  await expect(page.getByRole("checkbox")).toHaveCount(3)
})

test("The capture line writes into the narrowed project, and into the Inbox otherwise", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const project = await api.create("/projects/", { name: "Kitchen rebuild" })
  await api.create("/projects/", { name: "Shelved" })

  // Narrowed: it says where, and writes there.
  await page.goto(`/tasks?project_id=${project.id}`)
  const line = page.getByRole("textbox", {
    name: "Add a task to Kitchen rebuild",
  })
  await expect(line).toHaveAttribute(
    "placeholder",
    "Add a task to Kitchen rebuild…",
  )
  const sent = page.waitForRequest(
    (request) =>
      request.method() === "POST" && /\/tasks\/$/.test(request.url()),
  )
  await line.fill("Measure the alcove")
  await line.press("Enter")
  expect((await sent).postDataJSON()).toMatchObject({
    title: "Measure the alcove",
    project_id: project.id,
  })
  // At once, with a notice that offers Open and Undo, and the list has it.
  const made = notice(page).filter({ hasText: "created in Kitchen rebuild" })
  await expect(made).toContainText("“Measure the alcove” created")
  await expect(taskLine(page, "Measure the alcove")).toBeVisible()
  await expect(line).toHaveValue("")
  await made.getByRole("button", { name: "Undo" }).click()
  await expect(taskLine(page, "Measure the alcove")).toHaveCount(0)

  // Not narrowed: the Inbox, and the line says no project.
  await page.goto("/tasks")
  const plain = page.getByRole("textbox", { name: "Add a task", exact: true })
  await expect(plain).toHaveAttribute("placeholder", "Add a task…")
  await plain.fill("Pick up the parcel")
  await plain.press("Enter")
  const filed = notice(page).filter({ hasText: "created in Inbox" })
  await expect(filed).toContainText("“Pick up the parcel” created")
  await filed.getByRole("button", { name: "Open" }).click()
  await expect(
    page
      .getByRole("complementary", { name: "Pick up the parcel" })
      .getByRole("combobox", { name: "Project" }),
  ).toContainText("Inbox")
})

test("The navigation has no Add a task entry, and the c key still opens the full draft", async ({
  page,
}) => {
  await newUser(page)
  await page.goto("/tasks")

  const navigation = page.getByRole("navigation", { name: "Main" })
  await expect(navigation).toBeVisible()
  await expect(navigation.getByRole("button")).toHaveCount(0)
  await expect(navigation.getByText("Add a task")).toHaveCount(0)

  await page.keyboard.press("c")
  await expect(
    page.getByRole("complementary", { name: "New task" }),
  ).toBeVisible()
  await expect(page.getByRole("textbox", { name: "Task title" })).toBeFocused()
})

test("Every filter and the order are focusable buttons with names and a visible ring", async ({
  page,
}) => {
  await newUser(page)
  await seedTasks(page, 1)
  await page.goto("/tasks")

  const names = [
    "Any project",
    "Anyone",
    "Any status",
    "Any priority",
    "Any tag",
    "Any time",
    "Order: Newest first",
  ]
  for (const name of names) {
    await expect(page.getByRole("button", { name, exact: true })).toBeVisible()
  }

  // Reached by the keyboard alone, in the order they are read in, each with
  // a ring (a 2px outline) of its own.
  await page.getByRole("textbox", { name: "Add a task" }).focus()
  for (const name of names) {
    await page.keyboard.press("Tab")
    // The capture line's key cap is not focusable, and nothing else sits
    // between the line and the first filter except the heading's counts.
    const control = page.getByRole("button", { name, exact: true })
    await expect(control).toBeFocused()
    await expect(control).toHaveCSS("outline-style", "solid")
    await expect(control).toHaveCSS("outline-width", "2px")
  }
})

test("Down and Up walk the list in the order the lines are drawn", async ({
  page,
}) => {
  await newUser(page)
  const api = await userApi(page)
  const root = await api.create("/tasks/", { title: "Root" })
  await api.create("/tasks/", { title: "Later root" })
  await api.create("/tasks/", { title: "Child", parent_id: root.id })

  await page.goto("/tasks")
  // Drawn: Later root, Root, Child.
  await expect(lineTitles(page)).toHaveText(["Later root", "Root", "Child"])
  await taskLine(page, "Later root").getByRole("link").click()
  const column = (name: string) => page.getByRole("complementary", { name })
  await expect(column("Later root")).toContainText("1 of 3")

  await page.keyboard.press("ArrowDown")
  await expect(column("Root")).toContainText("2 of 3")
  await page.keyboard.press("ArrowDown")
  await expect(column("Child")).toContainText("3 of 3")
  await page.keyboard.press("ArrowUp")
  await expect(column("Root")).toContainText("2 of 3")
  await expect(
    taskLines(page).getByRole("link", { name: "Root", exact: true }),
  ).toHaveAttribute("aria-current", "page")
})
