import { useQuery } from "@tanstack/react-query"
import { List, SlidersHorizontal, Table2, X } from "lucide-react"
import { useState } from "react"

import type { TaskStatus } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ButtonGroup } from "@/components/ui/button-group"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { projectsQuery, tagsQuery } from "@/lib/serverState"
import { cn } from "@/lib/utils"
import { useBotUsers } from "./assignee"
import { PriorityOption } from "./priority"
import {
  clearedFilters,
  hasActiveFilters,
  isCompact,
  type TaskSearch,
} from "./search"
import {
  describeStatusFilter,
  isOpenFilter,
  OPEN_STATUSES,
  STATUS_LABELS,
  STATUSES,
} from "./statuses"
import { PRIORITIES } from "./writes"

// The status filter's choices: Open, or one status. Open is written to the
// URL as its three statuses, which is what the API filters on.
const OPEN = "open"

// A Select cannot hold an empty value, so "no filter" needs a name of its own.
// Everything selectable here is an id or a fixed keyword, never free text, so
// nothing a user types can collide with it.
const ANY = "any"

// The list's own order — subtasks under their parents — which no sort names.
const DEFAULT_ORDER = "default"

interface TaskFiltersProps {
  search: TaskSearch
  onChange: (next: Partial<TaskSearch>) => void
  /** Switch between the table and compact rows, without touching filters. */
  onViewChange: (view: TaskSearch["view"]) => void
}

/**
 * Compact rows or the table. The current one is marked the way the sidebar marks
 * where the reader is — a quiet fill, not the teal — since it is a place, not
 * an action.
 */
function ViewSwitch({
  view,
  onChange,
}: {
  view: TaskSearch["view"]
  onChange: (view: TaskSearch["view"]) => void
}) {
  const choices = [
    { value: undefined, label: "Compact", icon: List },
    { value: "table" as const, label: "Table", icon: Table2 },
  ]
  return (
    <ButtonGroup aria-label="View" className="ml-auto">
      {choices.map(({ value, label, icon: Icon }) => {
        const current = view === value
        return (
          <Button
            key={label}
            variant="outline"
            aria-pressed={current}
            onClick={() => onChange(value)}
            className={cn(
              "aria-pressed:bg-accent aria-pressed:text-accent-foreground",
              !current && "text-muted-foreground",
            )}
          >
            <Icon aria-hidden />
            <span className="hidden sm:inline">{label}</span>
            <span className="sr-only sm:hidden">{label}</span>
          </Button>
        )
      })}
    </ButtonGroup>
  )
}

interface Option {
  value: string
  label: string
  /** Drawn in the menu in place of the label, where the label needs a mark. */
  display?: React.ReactNode
}

function FilterSelect({
  label,
  anyLabel,
  value,
  options,
  onChange,
}: {
  label: string
  anyLabel: string
  value: string | undefined
  options: Option[]
  onChange: (value: string | undefined) => void
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label className="text-muted-foreground text-xs">{label}</Label>
      <Select
        value={value ?? ANY}
        onValueChange={(next) => onChange(next === ANY ? undefined : next)}
      >
        <SelectTrigger className="w-full" aria-label={label}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ANY}>{anyLabel}</SelectItem>
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.display ?? option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

function DateFilter({
  label,
  value,
  onChange,
}: {
  label: string
  value: string | undefined
  onChange: (value: string | undefined) => void
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label className="text-muted-foreground text-xs">{label}</Label>
      <Input
        type="date"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || undefined)}
      />
    </div>
  )
}

/**
 * Which choice the status select shows. A URL naming some other set of
 * statuses matches none of them; its chip still says what it filters.
 */
function statusValue(statuses: TaskStatus[] | undefined): string | undefined {
  if (!statuses) return undefined
  if (isOpenFilter(statuses)) return OPEN
  return statuses.length === 1 ? statuses[0] : undefined
}

/** One active filter, named in the reader's words, with the way to drop it. */
function ActiveChip({
  label,
  display,
  onRemove,
}: {
  label: string
  /** Drawn in place of the label; the label still names the remove button. */
  display?: React.ReactNode
  onRemove: () => void
}) {
  return (
    <Badge variant="secondary" className="gap-1 py-1 pr-1 pl-2.5">
      {display ?? label}
      <button
        type="button"
        aria-label={`Remove filter: ${label}`}
        onClick={onRemove}
        className="hover:bg-foreground/10 rounded-full p-0.5 transition-colors"
      >
        <X className="size-3" />
      </button>
    </Badge>
  )
}

/**
 * The filter bar over the task list.
 *
 * Sorting is not here: it belongs to the column it orders, where the reader
 * is already looking, and it is not a filter — clearing the filters must not
 * disturb the order.
 *
 * Every filter that is set narrows the list further — they combine with AND,
 * never OR (FR-06.3) — and each one lives in the URL, so a view can be shared
 * or reloaded.
 *
 * All eight filters at once is a wall of controls that mostly say "any", so
 * the panel is closed by default. What is closed is never hidden, though: an
 * active filter is always named on a chip that can drop it, because a list
 * silently narrowed by a control you cannot see is the worst outcome here.
 */
export function TaskFilters({
  search,
  onChange,
  onViewChange,
}: TaskFiltersProps) {
  const [isOpen, setIsOpen] = useState(false)
  const { data: bots } = useBotUsers()
  const { data: projects } = useQuery(projectsQuery())
  const { data: tags } = useQuery(tagsQuery())

  // Tag names are free text, so a tag could be called "any". Selecting by id
  // keeps the sentinel out of the user's namespace; the URL keeps the name.
  const tagOptions = (tags?.data ?? []).map((tag) => ({
    value: tag.id,
    label: tag.name,
  }))
  const selectedTagId = tagOptions.find(
    (option) => option.label === search.tag,
  )?.value
  const projectName = (id: string) =>
    projects?.data.find((project) => project.id === id)?.name ?? "Unknown"
  const assigneeName = (value: string) => {
    if (value === "me") return "Me"
    if (value === "unassigned") return "Unassigned"
    return bots?.data.find((bot) => bot.id === value)?.name ?? "A bot user"
  }

  /** Each active filter as a label plus the change that removes it. */
  const chips: {
    key: string
    label: string
    display?: React.ReactNode
    clear: Partial<TaskSearch>
  }[] = []
  if (search.project_id)
    chips.push({
      key: "project_id",
      label: `Project: ${projectName(search.project_id)}`,
      clear: { project_id: undefined },
    })
  if (search.assignee)
    chips.push({
      key: "assignee",
      label: `Assignee: ${assigneeName(search.assignee)}`,
      clear: { assignee: undefined },
    })
  if (search.tag)
    chips.push({
      key: "tag",
      label: `Tag: ${search.tag}`,
      clear: { tag: undefined },
    })
  if (search.priority)
    chips.push({
      key: "priority",
      label: `Priority: ${search.priority}`,
      display: (
        <span className="flex items-center gap-1">
          Priority: <PriorityOption priority={search.priority} />
        </span>
      ),
      clear: { priority: undefined },
    })
  const statusLabel = describeStatusFilter(search.status)
  if (statusLabel)
    chips.push({
      key: "status",
      label: `Status: ${statusLabel}`,
      clear: { status: undefined },
    })
  if (search.overdue)
    chips.push({
      key: "overdue",
      label: "Overdue",
      // Overdue asked for open work with it, so dropping it puts both back.
      clear: { overdue: undefined, status: undefined },
    })
  if (search.due_from)
    chips.push({
      key: "due_from",
      label: `Due from ${search.due_from}`,
      clear: { due_from: undefined },
    })
  if (search.due_to)
    chips.push({
      key: "due_to",
      label: `Due to ${search.due_to}`,
      clear: { due_to: undefined },
    })

  // Counted from the chips rather than from the schema keys, so the badge can
  // never claim a filter the reader has no chip for — an empty value in a
  // hand-edited URL is set but filters nothing.
  const activeCount = chips.length

  return (
    <div className="bg-card flex flex-col rounded-md border">
      <div className="flex flex-wrap items-center gap-2 p-3">
        <Button
          variant="outline"
          aria-expanded={isOpen}
          onClick={() => setIsOpen((open) => !open)}
        >
          <SlidersHorizontal />
          Filters
          {activeCount > 0 && (
            <Badge variant="secondary" className="ml-0.5 tabular-nums">
              {activeCount}
            </Badge>
          )}
        </Button>

        {/* Late work is open work, and the button says so in the URL as the
            Open status filter, where the reader can see and change it. */}
        <Button
          variant={search.overdue ? "default" : "outline"}
          onClick={() =>
            onChange(
              search.overdue
                ? { overdue: undefined, status: undefined }
                : { overdue: true, status: OPEN_STATUSES },
            )
          }
        >
          Overdue
        </Button>

        {/* On a phone the order and the view take a line of their own, the
            order stretching to fill it, so the bar wraps into two rows that
            line up rather than a ragged second one. */}
        <div
          className={cn(
            "ml-auto flex items-center gap-2",
            // The table has no order control here, and the view alone fits
            // on the first line.
            isCompact(search) && "w-full sm:w-auto",
          )}
        >
          {/* The table sorts from its headers; compact rows have none, so
              the same two orders are offered here instead. */}
          {isCompact(search) && (
            <Select
              value={search.sort ?? DEFAULT_ORDER}
              onValueChange={(next) =>
                onChange({
                  sort:
                    next === DEFAULT_ORDER
                      ? undefined
                      : (next as TaskSearch["sort"]),
                  order: undefined,
                })
              }
            >
              <SelectTrigger
                className="min-w-0 flex-1 sm:w-40 sm:flex-none"
                aria-label="Sort by"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={DEFAULT_ORDER}>Default order</SelectItem>
                <SelectItem value="due_date">Due date</SelectItem>
                <SelectItem value="priority">Priority</SelectItem>
              </SelectContent>
            </Select>
          )}
          <ViewSwitch view={search.view} onChange={onViewChange} />
        </div>
      </div>

      {isOpen && (
        <div className="grid gap-3 border-t p-3 sm:grid-cols-2 lg:grid-cols-4">
          <FilterSelect
            label="Project"
            anyLabel="Any project"
            value={search.project_id}
            options={(projects?.data ?? []).map((project) => ({
              value: project.id,
              label: project.name,
            }))}
            onChange={(project_id) => onChange({ project_id })}
          />
          <FilterSelect
            label="Assignee"
            anyLabel="Anyone"
            value={search.assignee}
            options={[
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
          <FilterSelect
            label="Tag"
            anyLabel="Any tag"
            value={selectedTagId}
            options={tagOptions}
            onChange={(id) =>
              onChange({
                tag: tagOptions.find((option) => option.value === id)?.label,
              })
            }
          />
          <FilterSelect
            label="Priority"
            anyLabel="Any priority"
            value={search.priority}
            options={PRIORITIES.map((priority) => ({
              value: priority,
              label: priority,
              display: <PriorityOption priority={priority} />,
            }))}
            onChange={(value) =>
              onChange({ priority: value as TaskSearch["priority"] })
            }
          />
          <FilterSelect
            label="Status"
            anyLabel="Any status"
            value={statusValue(search.status)}
            options={[
              { value: OPEN, label: "Open" },
              ...STATUSES.map((status) => ({
                value: status,
                label: STATUS_LABELS[status],
              })),
            ]}
            onChange={(value) =>
              onChange({
                status:
                  value === undefined
                    ? undefined
                    : value === OPEN
                      ? OPEN_STATUSES
                      : [value as TaskStatus],
              })
            }
          />
          <DateFilter
            label="Due from"
            value={search.due_from}
            onChange={(due_from) => onChange({ due_from })}
          />
          <DateFilter
            label="Due to"
            value={search.due_to}
            onChange={(due_to) => onChange({ due_to })}
          />
        </div>
      )}

      {chips.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 border-t p-3">
          {chips.map((chip) => (
            <ActiveChip
              key={chip.key}
              label={chip.label}
              display={chip.display}
              onRemove={() => onChange(chip.clear)}
            />
          ))}
          {hasActiveFilters(search) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onChange(clearedFilters())}
            >
              Clear all
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
