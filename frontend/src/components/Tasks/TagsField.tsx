import { useQuery } from "@tanstack/react-query"
import { X } from "lucide-react"
import { useId, useState } from "react"

import { TagsService } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"

interface TagsFieldProps
  extends Omit<React.ComponentProps<"input">, "value" | "onChange" | "list"> {
  value: string[]
  onChange: (tags: string[]) => void
}

/**
 * Tagging a task: type a name to add it, click a tag to drop it.
 *
 * Tags the user has already used are offered while they type, which is what
 * keeps one tag set from splintering into near-duplicates — there is no screen
 * for managing tags beyond this (FR-01.20).
 */
export function TagsField({ value, onChange, ...props }: TagsFieldProps) {
  const [draft, setDraft] = useState("")
  const suggestionsId = useId()

  // Let the server narrow the list: with many tags, fetching a page and
  // filtering it here would quietly stop offering the match further down.
  const { data: tags } = useQuery({
    queryKey: ["tags", draft],
    queryFn: async () =>
      (
        await TagsService.readTags({
          query: { q: draft || undefined, skip: 0, limit: 100 },
        })
      ).data,
  })

  const suggestions = (tags?.data ?? [])
    .map((tag) => tag.name)
    .filter((name) => !value.includes(name))

  const add = (name: string) => {
    const trimmed = name.trim()
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed])
    }
    setDraft("")
  }

  return (
    <div className="flex flex-col gap-2">
      <Input
        {...props}
        list={suggestionsId}
        placeholder="Type a tag and press Enter"
        value={draft}
        onChange={(e) => {
          const next = e.target.value
          // Picking a suggestion fires a change with the whole name, and a
          // comma is the other way people end a tag.
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
        onBlur={() => add(draft)}
      />
      <datalist id={suggestionsId}>
        {suggestions.map((name) => (
          <option key={name} value={name} />
        ))}
      </datalist>

      {value.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {value.map((name) => (
            <Badge key={name} variant="secondary" className="gap-1">
              {name}
              <button
                type="button"
                aria-label={`Remove tag ${name}`}
                className="cursor-pointer opacity-60 hover:opacity-100"
                onClick={() => onChange(value.filter((tag) => tag !== name))}
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
