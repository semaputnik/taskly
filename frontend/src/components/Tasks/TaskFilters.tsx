import { useQuery } from "@tanstack/react-query"
import { ArrowDownWideNarrow, ArrowUpNarrowWide, X } from "lucide-react"

import { ProjectsService, TagsService } from "@/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { clearedFilters, hasActiveFilters, type TaskSearch } from "./search"

// A Select cannot hold an empty value, so "no filter" needs a name of its own.
// Everything selectable here is an id or a fixed keyword, never free text, so
// nothing a user types can collide with it.
const ANY = "any"

interface TaskFiltersProps {
  search: TaskSearch
  onChange: (next: Partial<TaskSearch>) => void
}

interface Option {
  value: string
  label: string
}

/** A labelled select whose first entry means "don't filter on this". */
function FilterSelect({
  label,
  anyLabel,
  value,
  options,
  width,
  onChange,
}: {
  label: string
  anyLabel: string
  value: string | undefined
  options: Option[]
  width: string
  onChange: (value: string | undefined) => void
}) {
  return (
    <div className="flex flex-col gap-1">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Select
        value={value ?? ANY}
        onValueChange={(next) => onChange(next === ANY ? undefined : next)}
      >
        <SelectTrigger className={width}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ANY}>{anyLabel}</SelectItem>
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
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
    <div className="flex flex-col gap-1">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Input
        type="date"
        className="w-40"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || undefined)}
      />
    </div>
  )
}

/**
 * The filter and sort bar over the task list.
 *
 * Every filter that is set narrows the list further — they combine with AND,
 * never OR (FR-06.3) — and each one lives in the URL, so a view can be shared
 * or reloaded.
 */
export function TaskFilters({ search, onChange }: TaskFiltersProps) {
  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: async () =>
      (await ProjectsService.readProjects({ query: { skip: 0, limit: 100 } }))
        .data,
  })
  const { data: tags } = useQuery({
    queryKey: ["tags"],
    queryFn: async () =>
      (await TagsService.readTags({ query: { skip: 0, limit: 100 } })).data,
  })

  // Tag names are free text, so a tag could be called "any". Selecting by id
  // keeps the sentinel out of the user's namespace; the URL keeps the name.
  const tagOptions = (tags?.data ?? []).map((tag) => ({
    value: tag.id,
    label: tag.name,
  }))
  const selectedTagId = tagOptions.find(
    (option) => option.label === search.tag,
  )?.value

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-md border p-3">
      <FilterSelect
        label="Project"
        anyLabel="Any project"
        width="w-40"
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
        width="w-36"
        value={search.assignee}
        options={[
          { value: "me", label: "Me" },
          { value: "unassigned", label: "Unassigned" },
        ]}
        onChange={(value) =>
          onChange({ assignee: value as TaskSearch["assignee"] })
        }
      />

      <FilterSelect
        label="Tag"
        anyLabel="Any tag"
        width="w-36"
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
        width="w-32"
        value={search.priority}
        options={["P1", "P2", "P3", "P4"].map((priority) => ({
          value: priority,
          label: priority,
        }))}
        onChange={(value) =>
          onChange({ priority: value as TaskSearch["priority"] })
        }
      />

      <FilterSelect
        label="Status"
        anyLabel="Any status"
        width="w-36"
        value={
          search.completed === undefined ? undefined : String(search.completed)
        }
        options={[
          { value: "false", label: "Not completed" },
          { value: "true", label: "Completed" },
        ]}
        onChange={(value) =>
          onChange({
            completed: value === undefined ? undefined : value === "true",
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

      <Button
        variant={search.overdue ? "default" : "outline"}
        onClick={() =>
          // Late work people still care about is late work still open, so the
          // button asks for both — visibly, in the URL, rather than by having
          // one filter decide another.
          onChange(
            search.overdue
              ? { overdue: undefined, completed: undefined }
              : { overdue: true, completed: false },
          )
        }
      >
        Overdue
      </Button>

      <FilterSelect
        label="Sort by"
        anyLabel="Default"
        width="w-36"
        value={search.sort}
        options={[
          { value: "due_date", label: "Due date" },
          { value: "priority", label: "Priority" },
        ]}
        onChange={(value) => onChange({ sort: value as TaskSearch["sort"] })}
      />

      <Button
        variant="outline"
        size="icon"
        disabled={!search.sort}
        aria-label={
          search.order === "desc" ? "Sort ascending" : "Sort descending"
        }
        onClick={() =>
          onChange({ order: search.order === "desc" ? undefined : "desc" })
        }
      >
        {search.order === "desc" ? (
          <ArrowDownWideNarrow />
        ) : (
          <ArrowUpNarrowWide />
        )}
      </Button>

      {hasActiveFilters(search) && (
        <Button variant="ghost" onClick={() => onChange(clearedFilters())}>
          <X />
          Clear filters
        </Button>
      )}
    </div>
  )
}
