import { useQuery } from "@tanstack/react-query"
import { ChevronDown, X } from "lucide-react"
import type { ReactNode } from "react"

import { DayField } from "@/components/Common/DayField"
import { navItemFocus } from "@/components/Sidebar/styles"
import { Checkbox } from "@/components/ui/checkbox"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Label } from "@/components/ui/label"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { projectsQuery, tagsQuery } from "@/lib/serverState"
import { cn } from "@/lib/utils"
import { useBotUsers } from "./assignee"
import { orderChoice, timeLabel } from "./listWords"
import { PriorityOption } from "./priority"
import { clearedFilters, hasActiveFilters, type TaskSearch } from "./search"
import {
  describeStatusFilter,
  isOpenFilter,
  OPEN_STATUS_VALUES,
  type OpenStatus,
  STATUS_LABELS,
} from "./statuses"
import { PRIORITIES } from "./writes"

// A radio group cannot hold an empty value, so "no filter" needs a name of
// its own. Everything offered here is an id or a fixed keyword, never free
// text, so nothing a user types can collide with it.
const ANY = "any"

/**
 * One text button on the row, quiet until it is set: ink, a weight up, and an
 * × beside it that drops the filter. A button's focus is the navigation's
 * own: a 2px ink outline clear of it.
 */
const control = cn(
  navItemFocus,
  "text-ink-3 hover:bg-hover hover:text-ink data-[state=open]:bg-hover data-[state=open]:text-ink inline-flex h-7 items-center gap-[5px] rounded-md px-1.5 whitespace-nowrap transition-colors",
)

interface Choice {
  value: string
  label: string
  /** Drawn in the menu in place of the label, where the label needs a mark. */
  display?: ReactNode
}

/**
 * A filter as it sits on the row: its text, and when it is set the value in
 * place of "Any …" with the × that drops it. The two are separate buttons in
 * one pill, so the hover fill reads as one control.
 */
function Filter({
  noun,
  anyLabel,
  value,
  onRemove,
  menu,
}: {
  /** What is filtered, for the button's name: "Project". */
  noun: string
  anyLabel: string
  /** What the filter is set to, in the reader's words; none when it is not. */
  value: string | undefined
  onRemove: () => void
  /** Wraps the button in what it opens. */
  menu: (button: ReactNode) => ReactNode
}) {
  // An empty value in a hand-edited URL is set but narrows nothing, so it is
  // not drawn as a filter.
  const set = Boolean(value)
  const button = (
    <button
      type="button"
      aria-label={set ? `${noun}: ${value}` : undefined}
      className={cn(
        control,
        set && "text-ink font-medium",
        // The pill is the hover target when there is an × beside the text.
        set && "hover:bg-transparent data-[state=open]:bg-transparent",
      )}
    >
      {set ? value : anyLabel}
      {!set && <ChevronDown aria-hidden className="size-2.5 opacity-70" />}
    </button>
  )
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md",
        set && "hover:bg-hover pr-1",
      )}
    >
      {menu(button)}
      {set && (
        <button
          type="button"
          aria-label={`Remove the ${noun.toLowerCase()} filter`}
          onClick={onRemove}
          className={cn(
            navItemFocus,
            "text-ink-3 hover:bg-rule hover:text-ink grid size-3.5 place-items-center rounded-full transition-colors",
          )}
        >
          <X aria-hidden className="size-2.5" strokeWidth={2} />
        </button>
      )}
    </span>
  )
}

/** A filter that is one choice among a list: a menu of radio items. */
function ChoiceFilter({
  noun,
  anyLabel,
  value,
  selected,
  choices,
  onChange,
}: {
  noun: string
  anyLabel: string
  /** The set filter in the reader's words; none when the filter is not set. */
  value: string | undefined
  /** The value of the choice to mark, which is none for an odd URL's set. */
  selected: string | undefined
  choices: Choice[]
  /** The chosen value, or undefined for "any". */
  onChange: (value: string | undefined) => void
}) {
  return (
    <Filter
      noun={noun}
      anyLabel={anyLabel}
      value={value}
      onRemove={() => onChange(undefined)}
      menu={(button) => (
        <DropdownMenu modal={false}>
          <DropdownMenuTrigger asChild>{button}</DropdownMenuTrigger>
          <DropdownMenuContent align="start" aria-label={noun}>
            <DropdownMenuRadioGroup
              value={selected ?? (value ? "" : ANY)}
              onValueChange={(next) =>
                onChange(next === ANY ? undefined : next)
              }
            >
              <DropdownMenuRadioItem value={ANY}>
                {anyLabel}
              </DropdownMenuRadioItem>
              {choices.map((choice) => (
                <DropdownMenuRadioItem key={choice.value} value={choice.value}>
                  {choice.display ?? choice.label}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    />
  )
}

/**
 * Which choice the status menu marks. Every open status is the baseline, so
 * it is no narrowing at all. A URL naming some other set of them matches no
 * single choice; the button still says what it filters.
 */
function singleStatus(statuses: OpenStatus[] | undefined): string | undefined {
  if (!statuses || isOpenFilter(statuses)) return undefined
  return statuses.length === 1 ? statuses[0] : undefined
}

/**
 * The time filter: overdue, or a range of due dates. Two kinds of question in
 * one menu, since a day is all either one is about, and it is the only filter
 * that is not a pick from a list.
 */
function TimeFilter({
  search,
  onChange,
}: {
  search: TaskSearch
  onChange: (next: Partial<TaskSearch>) => void
}) {
  const label = timeLabel(search)
  return (
    <Filter
      noun="Time"
      anyLabel="Any time"
      value={label}
      onRemove={() =>
        onChange({ overdue: undefined, due_from: undefined, due_to: undefined })
      }
      menu={(button) => (
        <Popover>
          <PopoverTrigger asChild>{button}</PopoverTrigger>
          <PopoverContent align="start" aria-label="Time" className="w-64">
            <div className="flex flex-col gap-3.5">
              <Label className="gap-2.5 font-normal">
                <Checkbox
                  checked={search.overdue === true}
                  onCheckedChange={(checked) =>
                    onChange({ overdue: checked === true ? true : undefined })
                  }
                />
                Overdue
              </Label>
              <div className="flex flex-col gap-1.5">
                <Label className="text-ink-3 text-xs font-normal">
                  Due from
                </Label>
                <DayField
                  label="Due from"
                  value={search.due_from}
                  onChange={(day) => onChange({ due_from: day ?? undefined })}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label className="text-ink-3 text-xs font-normal">Due to</Label>
                <DayField
                  label="Due to"
                  value={search.due_to}
                  onChange={(day) => onChange({ due_to: day ?? undefined })}
                />
              </div>
            </div>
          </PopoverContent>
        </Popover>
      )}
    />
  )
}

type Sort = NonNullable<TaskSearch["sort"]>

/** The orders the list can be put in, the list's own first. */
const ORDERS: { sort: Sort | undefined; label: string }[] = [
  { sort: undefined, label: "Newest first" },
  { sort: "due_date", label: "Due date" },
  { sort: "priority", label: "Priority" },
  { sort: "created_at", label: "Filed" },
]

/**
 * The order menu, at the row's right. The list opens newest first with each
 * subtask under its root; the other three order it flat. Choosing one gives
 * it the direction it naturally runs in, and choosing it again reverses it,
 * which the menu says beside the order that is in force (FR-06.4).
 */
function OrderMenu({
  search,
  onOrder,
}: {
  search: TaskSearch
  onOrder: (sort: Sort | undefined) => void
}) {
  const { label } = orderChoice(search)
  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={`Order: ${label}`}
          className={cn(control, "-mr-1.5")}
        >
          {label}
          <ChevronDown aria-hidden className="size-2.5 opacity-70" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" aria-label="Order">
        <DropdownMenuRadioGroup value={search.sort ?? "default"}>
          {ORDERS.map(({ sort, label: name }) => (
            <DropdownMenuRadioItem
              key={sort ?? "default"}
              value={sort ?? "default"}
              // Chosen again it must reverse, so the item acts on selection
              // rather than on the group's change, which a repeat is not.
              onSelect={() => onOrder(sort)}
              className="gap-6"
            >
              {name}
              {sort && sort === search.sort && (
                <span className="text-ink-3 ml-auto text-xs">
                  Choose again to reverse
                </span>
              )}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/**
 * The row of filters over the task list, and the order menu at its end.
 *
 * Each filter is a quiet text button that opens a menu; one that is set is
 * said in ink, a weight up, in place of its "Any …", with an × to drop it.
 * Nothing is hidden by being closed: a set filter is always on the row, so
 * a list narrowed by a control you cannot see cannot happen. "Clear" at the
 * end of the filters drops them all and leaves the order alone.
 *
 * Every filter that is set narrows the list further — they combine with AND,
 * never OR (FR-06.3) — and each one lives in the URL, so a view can be shared
 * or reloaded.
 */
export function TaskFilters({
  search,
  onChange,
  onOrder,
}: {
  search: TaskSearch
  onChange: (next: Partial<TaskSearch>) => void
  onOrder: (sort: Sort | undefined) => void
}) {
  const { data: bots } = useBotUsers()
  const { data: projects } = useQuery(projectsQuery())
  const { data: tags } = useQuery(tagsQuery())

  const botName = (id: string) =>
    bots?.data.find((bot) => bot.id === id)?.name ?? "A bot user"
  const projectName = (id: string) =>
    projects
      ? (projects.data.find((project) => project.id === id)?.name ??
        "Unknown project")
      : "Project"
  // Tag names are free text, so a tag could be called "any". The menu holds
  // ids to keep the sentinel out of the reader's namespace; the URL keeps the
  // name, which is what the API filters by.
  const tagChoices = (tags?.data ?? []).map((tag) => ({
    value: tag.id,
    label: tag.name,
  }))

  const status = describeStatusFilter(search.status)

  return (
    <fieldset className="border-rule-strong m-0 min-w-0 text-ink-3 flex flex-wrap items-center gap-x-3 gap-y-1 border-0 border-b p-0 pb-2.5 text-[13.5px]">
      <legend className="sr-only">Filters</legend>
      <div className="-ml-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
        <ChoiceFilter
          noun="Project"
          anyLabel="Any project"
          value={search.project_id && projectName(search.project_id)}
          selected={search.project_id}
          choices={(projects?.data ?? []).map((project) => ({
            value: project.id,
            label: project.name,
          }))}
          onChange={(project_id) => onChange({ project_id })}
        />
        <ChoiceFilter
          noun="Assignee"
          anyLabel="Anyone"
          value={
            search.assignee === "me"
              ? "Assigned to me"
              : search.assignee === "unassigned"
                ? "Unassigned"
                : search.assignee && botName(search.assignee)
          }
          selected={search.assignee}
          choices={[
            { value: "me", label: "Me" },
            { value: "unassigned", label: "Unassigned" },
            ...(bots?.data ?? []).map((bot) => ({
              value: bot.id,
              label: bot.name,
            })),
          ]}
          onChange={(value) =>
            onChange({ assignee: value as TaskSearch["assignee"] })
          }
        />
        {/* Not on the row until a link asks for it: who filed a task is a
            question the lines answer themselves, and the row has room for
            the filters people reach for. A list narrowed to one still says
            so here, and it can be dropped. */}
        {search.reporter && (
          <ChoiceFilter
            noun="Created by"
            anyLabel="Anyone created"
            value={
              search.reporter === "me"
                ? "Created by me"
                : `Created by ${botName(search.reporter)}`
            }
            selected={search.reporter}
            choices={[
              { value: "me", label: "Me" },
              ...(bots?.data ?? []).map((bot) => ({
                value: bot.id,
                label: bot.name,
              })),
            ]}
            onChange={(value) =>
              onChange({ reporter: value as TaskSearch["reporter"] })
            }
          />
        )}
        {/* Done is not among the choices: the list holds open work, and
            finished work is read in the activity log (ADR-0006). Every open
            status is the baseline, so it is "Any status", not a filter. */}
        <ChoiceFilter
          noun="Status"
          anyLabel="Any status"
          value={status}
          selected={singleStatus(search.status)}
          choices={OPEN_STATUS_VALUES.map((value) => ({
            value,
            label: STATUS_LABELS[value],
          }))}
          onChange={(value) =>
            onChange({
              status: value === undefined ? undefined : [value as OpenStatus],
            })
          }
        />
        <ChoiceFilter
          noun="Priority"
          anyLabel="Any priority"
          value={search.priority}
          selected={search.priority}
          choices={PRIORITIES.map((priority) => ({
            value: priority,
            label: priority,
            display: <PriorityOption priority={priority} />,
          }))}
          onChange={(value) =>
            onChange({ priority: value as TaskSearch["priority"] })
          }
        />
        <ChoiceFilter
          noun="Tag"
          anyLabel="Any tag"
          value={search.tag}
          selected={tagChoices.find((tag) => tag.label === search.tag)?.value}
          choices={tagChoices}
          onChange={(id) =>
            onChange({ tag: tagChoices.find((tag) => tag.value === id)?.label })
          }
        />
        <TimeFilter search={search} onChange={onChange} />
      </div>
      {hasActiveFilters(search) && (
        <button
          type="button"
          aria-label="Clear all filters"
          onClick={() => onChange(clearedFilters())}
          className={cn(control, "-ml-1")}
        >
          Clear
        </button>
      )}
      <div className="ml-auto">
        <OrderMenu search={search} onOrder={onOrder} />
      </div>
    </fieldset>
  )
}
