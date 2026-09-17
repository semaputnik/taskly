import { useMutation, useQuery } from "@tanstack/react-query"
import { Bot, CheckSquare, Merge } from "lucide-react"
import { useState } from "react"

import { type TagPublic, TagsService } from "@/client"
import { NewRecord } from "@/components/Records/NewRecord"
import { useRecordPanel } from "@/components/Records/panels"
import {
  EditableText,
  PropertyList,
  PropertyRow,
  RecordHeader,
  RecordPanel,
  titleFieldClass,
  valueInset,
} from "@/components/Records/RecordPanel"
import { Button } from "@/components/ui/button"
import { Refusal, refusalCode } from "@/lib/apiErrors"
import { tagVocabularyQuery, useReportChange } from "@/lib/serverState"
import { toastError } from "@/lib/toasts"
import { BotCreator } from "./BotCreator"
import DeleteTag from "./DeleteTag"
import { MergeTags } from "./MergeTags"
import { TaskCount } from "./TaskCount"

/**
 * A tag as a record: its name, what carries it, and the two ways to make it
 * go — merging it with another spelling, or deleting it.
 *
 * A tag is a thin record and its panel is short. The value is that it has an
 * address and the same shape as every other record, not the amount in it.
 */
export function TagPanel() {
  const { capturing, record: tag, panels, shell } = useRecordPanel("tag")
  // A merge being considered from this panel, and the tag it was offered with
  // when a rename ran into that tag's name.
  const [merging, setMerging] = useState<{ with?: TagPublic } | null>(null)

  return (
    <RecordPanel
      {...shell}
      destructive={
        tag ? (
          <>
            {/* Merging is at the foot with deleting: both make this tag go,
                and neither is a property of it. */}
            <Button
              variant="ghost"
              size="sm"
              className="text-muted-foreground -ml-2.5 pointer-coarse:h-11"
              onClick={() => setMerging({})}
            >
              <Merge />
              Merge…
            </Button>
            <DeleteTag tag={tag} onSuccess={shell.onClose} />
          </>
        ) : undefined
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
          change={{ type: "tag created" }}
          onCreated={(created) => panels.openTag(created.id)}
        />
      ) : tag ? (
        <TagRecord
          tag={tag}
          onNameTaken={(taken) => setMerging({ with: taken })}
        />
      ) : null}
      {tag && merging && (
        <TagMerge
          tag={tag}
          offered={merging.with}
          onClose={() => setMerging(null)}
          onMerged={(survivor) => {
            // A merge that removed this tag moves the panel onto the one
            // that carries its tasks now.
            if (survivor.id !== tag.id) panels.openTag(survivor.id)
          }}
        />
      )}
    </RecordPanel>
  )
}

/** The merge dialog as a tag's panel opens it, with the whole vocabulary. */
function TagMerge({
  tag,
  offered,
  onClose,
  onMerged,
}: {
  tag: TagPublic
  offered?: TagPublic
  onClose: () => void
  onMerged: (survivor: TagPublic) => void
}) {
  const { data: vocabulary } = useQuery(tagVocabularyQuery())
  return (
    <MergeTags
      tags={offered ? [tag, offered] : [tag]}
      // The name the reader just asked for is the one to keep.
      initialSurvivorId={offered?.id ?? tag.id}
      candidates={(vocabulary ?? []).filter((other) => other.id !== tag.id)}
      onClose={onClose}
      onMerged={onMerged}
    />
  )
}

function TagRecord({
  tag,
  onNameTaken,
}: {
  tag: TagPublic
  onNameTaken: (taken: TagPublic) => void
}) {
  const reportChange = useReportChange()

  const rename = useMutation({
    mutationFn: (name: string) =>
      TagsService.renameTag({ path: { tag_id: tag.id }, body: { name } }),
    onError: (error) => toastError(error),
    // Renaming a tag renames it on every task carrying it (FR-01.24).
    onSettled: () => reportChange({ type: "tag changed" }),
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
              } catch (error) {
                // A name already in use is refused: the reader keeps theirs
                // and the toast says which name is taken (FR-01.22). Putting
                // the two together is a merge, which is offered here as the
                // separate, confirmed act it is — never done by the rename.
                if (refusalCode(error) === Refusal.TAG_EXISTS) {
                  const holder = (
                    await TagsService.readTags({
                      query: { near: trimmed, skip: 0, limit: 100 },
                    })
                  ).data.data.find((other) => other.name === trimmed)
                  if (holder) onNameTaken(holder)
                }
                return false
              }
            }}
            className={titleFieldClass}
          />
        }
      />

      <PropertyList>
        <PropertyRow icon={CheckSquare} label="Tasks">
          <TaskCount tag={tag} className={valueInset} />
        </PropertyRow>
        {tag.created_by_bot_user && (
          <PropertyRow icon={Bot} label="Created by">
            <span className={valueInset}>
              <BotCreator tag={tag} />
            </span>
          </PropertyRow>
        )}
      </PropertyList>
    </>
  )
}
