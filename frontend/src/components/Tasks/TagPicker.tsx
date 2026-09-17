import { useQuery } from "@tanstack/react-query"
import { Check, Plus, X } from "lucide-react"
import { useEffect, useState } from "react"

import { TagsService } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Command,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { cn } from "@/lib/utils"

/**
 * Tagging a task: the tags as chips on the property row, and one quiet button
 * that opens a popover to find, create and choose them.
 *
 * The row stays a label and a value, like every other property. Everything
 * that needs room — a search, the user's tags, near duplicates — lives in the
 * popover, which stays open so several tags can be set in one visit.
 *
 * A tag is added only by choosing a row: tags belong to the whole account, so
 * a fragment typed into the search and left behind by Escape, a click outside
 * or Tab must never become one. What is typed is a query, not data. The user's
 * own tags are offered as they type, and a new name that only differs in form
 * from one they have (FR-01.28) is steered to it before it is created — which
 * is what keeps one tag set from splintering. A name that is not a tag yet
 * becomes one when its create row is chosen (FR-01.20); renaming and deleting
 * tags is on the Tags page.
 */

// Row values, prefixed so a tag called "create" cannot collide with the row
// that creates one.
const CREATE = "create:"
const TAG = "tag:"
const NEAR = "near:"

interface TagPickerContentProps {
  /** Tags to show as already chosen, with a ✓ that toggles them off. */
  chosen: readonly string[]
  /**
   * `toggle`: choosing a chosen tag takes it off. `add`: every choice is an
   * addition, for a selection whose tasks carry different tags.
   */
  mode: "toggle" | "add"
  onAdd: (name: string) => void
  onRemove?: (name: string) => void
}

/**
 * The popover's content: search, the user's tags, near duplicates, and the
 * row that creates a new tag. Shared by the task panel and bulk actions.
 */
export function TagPickerContent({
  chosen,
  mode,
  onAdd,
  onRemove,
}: TagPickerContentProps) {
  const [search, setSearch] = useState("")
  const name = search.trim()

  // The server narrows the list: with many tags, fetching a page and
  // filtering it here would quietly stop offering the match further down.
  const { data: tags } = useQuery({
    queryKey: ["tags", name],
    queryFn: async () =>
      (
        await TagsService.readTags({
          query: { q: name || undefined, skip: 0, limit: 100 },
        })
      ).data,
  })
  const names = (tags?.data ?? []).map((tag) => tag.name)
  // Tag names match exactly, as the server matches them. Until the answer for
  // this very name is in, nothing is offered for creation.
  const answered = tags !== undefined
  const exact = names.includes(name)

  // Spellings a new name would read the same as — "Deploys" beside "deploy" —
  // asked once typing pauses, and only when the name is not a tag already.
  const settled = useDebouncedValue(name, 250)
  const { data: near } = useQuery({
    queryKey: ["tags", "near", settled],
    queryFn: async () =>
      (
        await TagsService.readTags({
          query: { near: settled, skip: 0, limit: 5 },
        })
      ).data,
    enabled: Boolean(settled) && settled === name && answered && !exact,
  })
  const nearMatches =
    !name || exact || settled !== name
      ? []
      : (near?.data ?? [])
          .map((tag) => tag.name)
          .filter((tagName) => tagName !== name && !chosen.includes(tagName))
  const listed = names.filter((tagName) => !nearMatches.includes(tagName))
  const creates = Boolean(name) && answered && !exact

  // Enter does what it did in the old field: attach the exact match, or
  // create the name. Arrows move on from there.
  const defaultRow = !name
    ? ""
    : exact
      ? `${TAG}${name}`
      : creates
        ? `${CREATE}${name}`
        : ""
  const [highlight, setHighlight] = useState(defaultRow)
  useEffect(() => setHighlight(defaultRow), [defaultRow])

  const choose = (tagName: string) => {
    if (chosen.includes(tagName)) {
      if (mode === "toggle") onRemove?.(tagName)
      return
    }
    onAdd(tagName)
  }

  return (
    // The server has already filtered; the list's own matching would fight it.
    <Command
      shouldFilter={false}
      value={highlight}
      onValueChange={setHighlight}
    >
      <CommandInput
        aria-label="Search or create a tag"
        placeholder="Search or create a tag"
        value={search}
        onValueChange={setSearch}
      />
      <CommandList>
        {listed.length > 0 && (
          <CommandGroup>
            {listed.map((tagName) => (
              <CommandItem
                key={tagName}
                value={`${TAG}${tagName}`}
                onSelect={() => choose(tagName)}
              >
                <Check
                  className={cn(
                    "text-foreground",
                    !chosen.includes(tagName) && "invisible",
                  )}
                  aria-hidden
                />
                <span className="truncate">{tagName}</span>
                {chosen.includes(tagName) && (
                  <span className="sr-only">(on it)</span>
                )}
              </CommandItem>
            ))}
          </CommandGroup>
        )}
        {nearMatches.length > 0 && (
          <CommandGroup heading="You already have">
            {nearMatches.map((tagName) => (
              <CommandItem
                key={tagName}
                value={`${NEAR}${tagName}`}
                onSelect={() => {
                  choose(tagName)
                  setSearch("")
                }}
              >
                <Check className="invisible" aria-hidden />
                <span className="truncate">{tagName}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        )}
        {creates && (
          <CommandGroup>
            <CommandItem
              value={`${CREATE}${name}`}
              onSelect={() => {
                choose(name)
                setSearch("")
              }}
            >
              <Plus aria-hidden />
              <span className="truncate">Create tag "{name}"</span>
            </CommandItem>
          </CommandGroup>
        )}
        {answered && !listed.length && !nearMatches.length && !creates && (
          <p className="text-muted-foreground px-3 py-6 text-center text-sm">
            No tags yet. Type a name to create one.
          </p>
        )}
      </CommandList>
    </Command>
  )
}

/** Where on a narrow screen the popover spans the panel. */
const popoverClass = "w-72 p-0 max-sm:w-[calc(100vw-2rem)]"

/**
 * A task's tags as a property value: chips, then the Add tag button.
 *
 * The value it reports is the whole set, built on what the reader has
 * already chosen in this visit, so a second choice made before the first
 * save comes back cannot drop the first.
 */
export function TagPicker({
  value,
  onChange,
}: {
  value: string[]
  onChange: (tags: string[]) => void
}) {
  const [open, setOpen] = useState(false)
  const [current, setCurrent] = useState(value)
  const [announcement, setAnnouncement] = useState("")
  useEffect(() => setCurrent(value), [value])

  const set = (next: string[], said: string) => {
    setCurrent(next)
    setAnnouncement(said)
    onChange(next)
  }
  const add = (tagName: string) =>
    set([...current, tagName], `${tagName} added`)
  const remove = (tagName: string) =>
    set(
      current.filter((tag) => tag !== tagName),
      `${tagName} removed`,
    )

  return (
    <div className="flex flex-wrap items-center gap-1 py-0.5">
      {current.map((tagName) => (
        <Badge key={tagName} variant="secondary" className="gap-1">
          {tagName}
          <button
            type="button"
            aria-label={`Remove tag ${tagName}`}
            className="-my-1 -mr-1 inline-flex size-6 cursor-pointer items-center justify-center rounded-sm opacity-60 hover:opacity-100 pointer-coarse:-my-3 pointer-coarse:size-11"
            onClick={() => remove(tagName)}
          >
            <X className="size-3" />
          </button>
        </Badge>
      ))}
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-muted-foreground pointer-coarse:h-11"
          >
            <Plus />
            Add tag
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className={popoverClass}>
          {/* Mounted only while open, so a query typed and abandoned is gone
              the next time. */}
          <TagPickerContent
            chosen={current}
            mode="toggle"
            onAdd={add}
            onRemove={remove}
          />
        </PopoverContent>
      </Popover>
      {/* The change happens behind the popover, so it is said as well. */}
      <output aria-live="polite" className="sr-only">
        {announcement}
      </output>
    </div>
  )
}

/**
 * Add tag for a selection: each choice adds that tag to every selected task
 * at once, and is marked until the popover closes, so the reader sees what
 * was applied. The tasks' own tags are not shown — they differ.
 */
export function BulkTagPicker({ onAdd }: { onAdd: (name: string) => void }) {
  const [open, setOpen] = useState(false)
  const [applied, setApplied] = useState<string[]>([])
  const [announcement, setAnnouncement] = useState("")

  return (
    <>
      <Popover
        open={open}
        onOpenChange={(next) => {
          setOpen(next)
          if (!next) setApplied([])
        }}
      >
        <PopoverTrigger asChild>
          <Button type="button" variant="outline" size="sm">
            <Plus />
            Add tag
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className={popoverClass}>
          <TagPickerContent
            chosen={applied}
            mode="add"
            onAdd={(tagName) => {
              setApplied((previous) => [...previous, tagName])
              setAnnouncement(`${tagName} added`)
              onAdd(tagName)
            }}
          />
        </PopoverContent>
      </Popover>
      <output aria-live="polite" className="sr-only">
        {announcement}
      </output>
    </>
  )
}
