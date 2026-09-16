import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import { Bot, CheckSquare, Merge } from "lucide-react"
import { useState } from "react"

import { type TagPublic, TagsService } from "@/client"
import { NewRecord } from "@/components/Records/NewRecord"
import {
  EditableText,
  ghost,
  PropertyList,
  PropertyRow,
  ReadOnlyValue,
  RecordHeader,
  RecordPanel,
  recordLoad,
  titleFieldClass,
} from "@/components/Records/RecordPanel"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"
import { BotCreator } from "./BotCreator"
import { archivedNote, tasks } from "./counts"
import DeleteTag from "./DeleteTag"
import { MergeTags } from "./MergeTags"

/**
 * A tag as a record: its name, what carries it, and the one way to remove it.
 *
 * A tag is a thin record and its panel is short. The value is that it has an
 * address and the same shape as every other record, not the amount in it.
 */
export function TagPanel({
  tagId,
  capturing,
  onClose,
  onCreated,
  onOpenTag,
}: {
  tagId: string | null
  capturing: boolean
  onClose: () => void
  onCreated: (tag: TagPublic) => void
  onOpenTag: (tagId: string) => void
}) {
  const query = useQuery({
    queryKey: ["tag", tagId],
    queryFn: async () =>
      (await TagsService.readTag({ path: { tag_id: tagId as string } })).data,
    enabled: Boolean(tagId),
  })
  const tag = query.data

  return (
    <RecordPanel
      open={Boolean(tagId) || capturing}
      onClose={onClose}
      name={capturing ? "New tag" : (tag?.name ?? "Tag")}
      kind="tag"
      {...recordLoad(query, !capturing && Boolean(tagId))}
      destructive={
        tag ? <DeleteTag tag={tag} onSuccess={onClose} /> : undefined
      }
    >
      {capturing ? (
        <NewRecord
          kind="Tag"
          label="Tag name"
          placeholder="What does it gather?"
          hint="Enter creates it and opens it here. A tag means the same thing across every project, and stays until you delete it."
          create={(name) =>
            TagsService.createTag({ body: { name } }) as Promise<{
              data: TagPublic
            }>
          }
          invalidate={["tags"]}
          onCreated={onCreated}
        />
      ) : tag ? (
        <TagRecord tag={tag} openTag={onOpenTag} />
      ) : null}
    </RecordPanel>
  )
}

function TagRecord({
  tag,
  openTag,
}: {
  tag: TagPublic
  openTag: (tagId: string) => void
}) {
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  // The other tag a merge is being considered with, and which name it keeps.
  const [mergeWith, setMergeWith] = useState<TagPublic | null>(null)
  const [survivorId, setSurvivorId] = useState<string>()
  const openMerge = (other: TagPublic, keep: TagPublic) => {
    setMergeWith(other)
    setSurvivorId(keep.id)
  }

  const { data: vocabulary } = useQuery({
    queryKey: ["tags", "all", { skip: 0, limit: 1000 }],
    queryFn: async () =>
      (await TagsService.readTags({ query: { skip: 0, limit: 1000 } })).data,
  })
  const others = (vocabulary?.data ?? []).filter((other) => other.id !== tag.id)
  // The tag holding a name, asked of the server when the vocabulary has not
  // arrived yet: a refusal can come quicker than the list.
  const takenBy = async (name: string) =>
    others.find((other) => other.name === name) ??
    (
      await TagsService.readTags({ query: { q: name, skip: 0, limit: 100 } })
    ).data.data.find((other) => other.name === name && other.id !== tag.id)

  const rename = useMutation({
    mutationFn: (name: string) =>
      TagsService.renameTag({ path: { tag_id: tag.id }, body: { name } }),
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tags"] })
      queryClient.invalidateQueries({ queryKey: ["tag", tag.id] })
      // Renaming a tag renames it on every task carrying it (FR-01.24).
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
    },
  })

  return (
    <>
      <RecordHeader
        breadcrumb="Tag"
        title={
          <EditableText
            value={tag.name}
            ariaLabel="Tag name"
            onCommit={async (name) => {
              const trimmed = name.trim()
              if (!trimmed) return false
              try {
                await rename.mutateAsync(trimmed)
                return true
              } catch {
                // A name already in use is refused: the reader keeps theirs
                // and the toast says which name is taken (FR-01.22). Putting
                // the two together is a merge, which is offered here as the
                // separate, confirmed act it is — never done by the rename.
                const taken = await takenBy(trimmed)
                if (taken) openMerge(taken, taken)
                return false
              }
            }}
            className={titleFieldClass}
          />
        }
      />

      <PropertyList>
        <PropertyRow icon={CheckSquare} label="Tasks">
          <span className="flex flex-wrap items-baseline gap-x-2">
            {(tag.task_count ?? 0) > 0 ? (
              <RouterLink
                to="/tasks"
                search={{ tag: tag.name }}
                className="px-2 underline-offset-4 hover:underline"
              >
                {tasks(tag.task_count ?? 0)}
              </RouterLink>
            ) : (
              <ReadOnlyValue>No tasks</ReadOnlyValue>
            )}
            {archivedNote(tag) && (
              <span className="text-muted-foreground text-xs">
                {archivedNote(tag)}
              </span>
            )}
          </span>
        </PropertyRow>
        {tag.created_by_bot_user && (
          <PropertyRow icon={Bot} label="Created by">
            <span className="px-2">
              <BotCreator tag={tag} />
            </span>
          </PropertyRow>
        )}
        <PropertyRow icon={Merge} label="Merge" htmlFor={`merge-${tag.id}`}>
          <Select
            value=""
            disabled={others.length === 0}
            onValueChange={(otherId) => {
              const other = others.find((candidate) => candidate.id === otherId)
              if (other) openMerge(other, other)
            }}
          >
            <SelectTrigger
              id={`merge-${tag.id}`}
              className={cn(ghost, "w-full")}
            >
              <SelectValue
                placeholder={
                  others.length === 0
                    ? "No other tag to merge with"
                    : "Merge with another tag…"
                }
              />
            </SelectTrigger>
            <SelectContent>
              {others.map((other) => (
                <SelectItem key={other.id} value={other.id}>
                  {other.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </PropertyRow>
      </PropertyList>

      {mergeWith && (
        <MergeTags
          open={Boolean(mergeWith)}
          onOpenChange={(open) => !open && setMergeWith(null)}
          tags={[tag, mergeWith]}
          initialSurvivorId={survivorId}
          onMerged={(survivor) => {
            // A merge that removed this tag moves the panel onto the one
            // that carries its tasks now.
            if (survivor.id !== tag.id) openTag(survivor.id)
          }}
        />
      )}
    </>
  )
}
