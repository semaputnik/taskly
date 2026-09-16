import { useQuery } from "@tanstack/react-query"
import { X } from "lucide-react"
import { useId, useState } from "react"

import { TagsService } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { cn } from "@/lib/utils"

interface TagsFieldProps
  extends Omit<React.ComponentProps<"input">, "value" | "onChange" | "list"> {
  value: string[]
  onChange: (tags: string[]) => void
  /**
   * Hang the note on what Enter will do beneath the field instead of in the
   * flow, for a toolbar whose controls must stay on one line.
   */
  floatingHint?: boolean
}

/**
 * Tagging a task: type a name to add it, click a tag to drop it.
 *
 * The user's tags are offered while they type, which is what keeps one tag set
 * from splintering into near-duplicates. A name that is not a tag yet becomes
 * one (FR-01.20); renaming and deleting tags is on the Tags page.
 *
 * A tag is added only by a deliberate gesture — Enter, a comma, or picking a
 * suggestion — never by leaving the field: tags belong to the whole account,
 * so a fragment committed by a stray Tab would outlive the task it landed on.
 * Before anything is added, the field says whether the name is a tag the user
 * already has or one it would create.
 */
export function TagsField({
  value,
  onChange,
  floatingHint = false,
  ...props
}: TagsFieldProps) {
  const [draft, setDraft] = useState("")
  // Focus left while the field still held a name nobody added.
  const [leftUnsent, setLeftUnsent] = useState(false)
  const suggestionsId = useId()
  const hintId = useId()
  const name = draft.trim()

  // Let the server narrow the list: with many tags, fetching a page and
  // filtering it here would quietly stop offering the match further down.
  // Asked by the name as it will be saved, so a trailing space does not hide
  // the tag it would attach.
  const { data: tags } = useQuery({
    queryKey: ["tags", name],
    queryFn: async () =>
      (
        await TagsService.readTags({
          query: { q: name || undefined, skip: 0, limit: 100 },
        })
      ).data,
  })

  const exists = tags?.data.some((tag) => tag.name === name)
  // The spellings a new name would read the same as — "Deploys" beside
  // "deploy" — offered before it is created, each keeping its own casing
  // (FR-01.28).
  // Asked once typing pauses rather than on every keystroke.
  const settledName = useDebouncedValue(name, 250)
  const { data: near } = useQuery({
    queryKey: ["tags", "near", settledName],
    queryFn: async () =>
      (
        await TagsService.readTags({
          query: { near: settledName, skip: 0, limit: 5 },
        })
      ).data,
    enabled:
      Boolean(settledName) &&
      settledName === name &&
      exists === false &&
      !value.includes(name),
  })
  const nearMatches =
    exists || settledName !== name
      ? []
      : (near?.data ?? [])
          .map((tag) => tag.name)
          .filter((tagName) => tagName !== name && !value.includes(tagName))

  const suggestions = (tags?.data ?? [])
    .map((tag) => tag.name)
    .filter((tagName) => !value.includes(tagName))

  const add = (raw: string) => {
    const trimmed = raw.trim()
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed])
    }
    setDraft("")
    setLeftUnsent(false)
  }

  // Tag names match exactly, as the server matches them. Until the answer for
  // this very name is in, the field says nothing rather than guess.
  const hint = !name
    ? null
    : value.includes(name)
      ? `${name} is already on it.`
      : !tags
        ? null
        : exists
          ? `Enter adds your tag ${name}.`
          : `Enter creates a new tag, ${name}.`

  return (
    <div className="relative flex flex-col gap-1">
      <Input
        {...props}
        list={suggestionsId}
        placeholder="Type a tag and press Enter"
        aria-describedby={hintId}
        value={draft}
        onChange={(e) => {
          const next = e.target.value
          setLeftUnsent(false)
          // Picking a suggestion is a choice, so it adds the tag; the browser
          // reports it as a replacement of the whole value rather than typing.
          const native = e.nativeEvent as InputEvent
          const picked =
            !(native instanceof InputEvent) ||
            native.inputType === "insertReplacementText"
          if (picked && suggestions.includes(next)) {
            add(next)
            return
          }
          // A comma is the other way people end a tag.
          if (next.endsWith(",")) {
            add(next.slice(0, -1))
            return
          }
          setDraft(next)
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            // The field sits inside a form; adding a tag must not submit it.
            e.preventDefault()
            add(draft)
          }
          if (e.key === "Backspace" && !draft && value.length) {
            onChange(value.slice(0, -1))
          }
        }}
        onBlur={() => setLeftUnsent(Boolean(name))}
      />
      <datalist id={suggestionsId}>
        {suggestions.map((tagName) => (
          <option key={tagName} value={tagName} />
        ))}
      </datalist>
      <p
        id={hintId}
        aria-live="polite"
        className={cn(
          "text-muted-foreground px-2 text-xs empty:hidden",
          floatingHint && "absolute top-full left-0 mt-1 whitespace-nowrap",
        )}
      >
        {leftUnsent && hint ? `Not added yet. ${hint}` : hint}
        {hint && nearMatches.length > 0 && (
          <> You already have {nearMatches.join(", ")}.</>
        )}
      </p>
      {hint && nearMatches.length > 0 && (
        <div className="flex flex-wrap gap-1 px-1">
          {nearMatches.map((tagName) => (
            <Button
              key={tagName}
              type="button"
              variant="outline"
              size="sm"
              className="h-7 pointer-coarse:h-11"
              // Picking keeps the reader in the field, ready for the next tag.
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => add(tagName)}
            >
              Use {tagName}
            </Button>
          ))}
        </div>
      )}

      {value.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {value.map((tagName) => (
            <Badge key={tagName} variant="secondary" className="gap-1">
              {tagName}
              <button
                type="button"
                aria-label={`Remove tag ${tagName}`}
                className="-my-1 -mr-1 inline-flex cursor-pointer items-center justify-center rounded-sm p-1 opacity-60 hover:opacity-100 pointer-coarse:-my-3 pointer-coarse:size-11"
                onClick={() => onChange(value.filter((tag) => tag !== tagName))}
              >
                <X className="size-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  )
}
