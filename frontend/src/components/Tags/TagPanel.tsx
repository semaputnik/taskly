import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import { CheckSquare } from "lucide-react"

import { type TagPublic, TagsService } from "@/client"
import { NewRecord } from "@/components/Records/NewRecord"
import {
  EditableText,
  PropertyList,
  PropertyRow,
  ReadOnlyValue,
  RecordHeader,
  RecordPanel,
  titleFieldClass,
} from "@/components/Records/RecordPanel"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import DeleteTag from "./DeleteTag"

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
}: {
  tagId: string | null
  capturing: boolean
  onClose: () => void
  onCreated: (tag: TagPublic) => void
}) {
  const {
    data: tag,
    isPending,
    isError,
  } = useQuery({
    queryKey: ["tag", tagId],
    queryFn: async () =>
      (await TagsService.readTag({ path: { tag_id: tagId as string } })).data,
    enabled: Boolean(tagId),
  })

  return (
    <RecordPanel
      open={Boolean(tagId) || capturing}
      onClose={onClose}
      name={capturing ? "New tag" : (tag?.name ?? "Tag")}
      kind="tag"
      missing={!capturing && Boolean(tagId) && isError}
      pending={!capturing && Boolean(tagId) && isPending}
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
        <TagRecord tag={tag} />
      ) : null}
    </RecordPanel>
  )
}

function TagRecord({ tag }: { tag: TagPublic }) {
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

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
                // and the toast says which name is taken (FR-01.22).
                return false
              }
            }}
            className={titleFieldClass}
          />
        }
      />

      <PropertyList>
        <PropertyRow icon={CheckSquare} label="Tasks">
          {(tag.task_count ?? 0) > 0 ? (
            <RouterLink
              to="/tasks"
              search={{ tag: tag.name }}
              className="px-2 underline-offset-4 hover:underline"
            >
              {tag.task_count === 1 ? "1 task" : `${tag.task_count} tasks`}
            </RouterLink>
          ) : (
            <ReadOnlyValue>No tasks</ReadOnlyValue>
          )}
        </PropertyRow>
      </PropertyList>
    </>
  )
}
