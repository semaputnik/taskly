import { useMutation, useQuery } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import { useState } from "react"

import { type TagPublic, TagsService } from "@/client"
import { act } from "@/components/Common/RecordWork"
import { useRecordPanel } from "@/components/Records/panels"
import {
  EditableText,
  gutter,
  PropertyList,
  PropertyRow,
  quiet,
  ReadOnlyValue,
  RecordPanel,
  titleFieldClass,
} from "@/components/Records/RecordPanel"
import { useWalk } from "@/components/Records/walk"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Refusal, refusalCode, refusalMessage } from "@/lib/apiErrors"
import { formatDayOf, inSentence } from "@/lib/dates"
import { tagVocabularyQuery, useReportChange } from "@/lib/serverState"
import { cn } from "@/lib/utils"
import DeleteTag from "./DeleteTag"
import { MergeTags } from "./MergeTags"
import { NewTag } from "./NewTag"
import { OpenTasks } from "./TagWork"
import { deletionReach, tasksInWords } from "./words"

/** A merge being considered, and which of its two names the reader keeps. */
interface Merging {
  with: TagPublic
  keep: "this" | "other"
}

/**
 * A tag as one document: what carries it, a way to fold another tag into it,
 * its first open tasks, and at the foot the one way to make it go.
 *
 * A tag is a thin record and its column is short. The value is that it has an
 * address and the same shape as every other record, not the amount in it.
 */
export function TagPanel() {
  const { id, capturing, record: tag, panels, shell } = useRecordPanel("tag")
  // The tags listed on the page behind, so ↓ and ↑ walk them.
  const walk = useWalk(id)
  // A merge being considered from this column: the tag chosen to fold in, or
  // the one a rename ran into the name of.
  const [merging, setMerging] = useState<Merging | null>(null)

  return (
    <RecordPanel
      {...shell}
      walk={walk}
      onWalk={(to) => panels.walkTo(to, "tag")}
      destructive={
        tag && !capturing ? (
          <>
            <DeleteTag tag={tag} onSuccess={shell.onClose} />
            <span className="text-ink-3 self-center text-[13px] text-pretty">
              {deletionReach(tag)}
            </span>
          </>
        ) : undefined
      }
      bar={
        capturing ? (
          <>
            <span className="shrink-0">New tag</span>
            <span aria-hidden>·</span>
            <span className="truncate">Not saved yet</span>
          </>
        ) : tag ? (
          <>
            <span className="shrink-0">Tag</span>
            {tag.created_at && (
              <>
                <span aria-hidden>·</span>
                <span className="truncate">
                  created {inSentence(formatDayOf(tag.created_at))}
                  {tag.created_by_bot_user &&
                    ` by ${tag.created_by_bot_user.name}`}
                </span>
              </>
            )}
          </>
        ) : undefined
      }
    >
      {capturing ? (
        <NewTag />
      ) : tag ? (
        <TagRecord
          key={tag.id}
          tag={tag}
          onNameTaken={(taken) => setMerging({ with: taken, keep: "other" })}
          onFold={(other) => setMerging({ with: other, keep: "this" })}
        />
      ) : null}
      {tag && merging && (
        <TagMerge
          tag={tag}
          merging={merging}
          onClose={() => setMerging(null)}
          onMerged={(survivor) => {
            // A merge that removed this tag moves the column onto the one
            // that carries its tasks now.
            if (survivor.id !== tag.id) panels.openTag(survivor.id)
          }}
        />
      )}
    </RecordPanel>
  )
}

/** The confirmation of a merge as a tag's column opens it. */
function TagMerge({
  tag,
  merging,
  onClose,
  onMerged,
}: {
  tag: TagPublic
  merging: Merging
  onClose: () => void
  onMerged: (survivor: TagPublic) => void
}) {
  const { data: vocabulary } = useQuery(tagVocabularyQuery())
  return (
    <MergeTags
      tags={[tag, merging.with]}
      // Folding another tag in keeps this one; a rename that ran into a name
      // in use keeps the name the reader asked for.
      initialSurvivorId={merging.keep === "this" ? tag.id : merging.with.id}
      candidates={(vocabulary ?? []).filter((other) => other.id !== tag.id)}
      onClose={onClose}
      onMerged={onMerged}
    />
  )
}

function TagRecord({
  tag,
  onNameTaken,
  onFold,
}: {
  tag: TagPublic
  onNameTaken: (taken: TagPublic) => void
  onFold: (other: TagPublic) => void
}) {
  const reportChange = useReportChange()
  // Why the last name the reader typed was refused. The words stay in the
  // field; this says what is wrong with them.
  const [refusal, setRefusal] = useState<string | null>(null)

  const rename = useMutation({
    mutationFn: (name: string) =>
      TagsService.renameTag({ path: { tag_id: tag.id }, body: { name } }),
    // A refusal is said under the name, where the reader's words stay.
    // Renaming a tag renames it on every task carrying it (FR-01.24).
    onSettled: () => reportChange({ type: "tag changed" }),
  })

  const open = tag.task_count ?? 0

  return (
    <>
      <div className={cn("pt-2 pb-[18px]", gutter)}>
        <EditableText
          value={tag.name}
          ariaLabel="Tag name"
          onCommit={async (name) => {
            const trimmed = name.trim()
            if (!trimmed) {
              setRefusal("A tag needs a name.")
              return false
            }
            try {
              await rename.mutateAsync(trimmed)
              setRefusal(null)
              return true
            } catch (error) {
              setRefusal(refusalMessage(error))
              // A name already in use is refused: the reader keeps theirs
              // and says which name is taken (FR-01.22). Putting the two
              // together is a merge, which is offered here as the separate,
              // confirmed act it is — never done by the rename.
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
          className={cn(titleFieldClass, "-ml-2")}
        />
        {refusal && (
          <p role="alert" className="text-late mt-1 text-[13px] text-pretty">
            {refusal}
          </p>
        )}
      </div>

      <PropertyList>
        <PropertyRow label="Tasks">
          <span className="text-ink-2 text-sm tabular-nums">
            {tasksInWords(tag)}
          </span>
          {open > 0 && (
            <RouterLink to="/tasks" search={{ tag: tag.name }} className={act}>
              Open the list <span aria-hidden>→</span>
            </RouterLink>
          )}
        </PropertyRow>

        <PropertyRow label="Merge">
          <FoldIn tag={tag} onChoose={onFold} />
        </PropertyRow>
      </PropertyList>

      <OpenTasks key={`tasks-${tag.id}`} tag={tag} />
    </>
  )
}

/**
 * "Fold another tag into this one: choose a tag…". Choosing is the first step
 * of a merge, not the merge: it opens the confirmation that names the numbers.
 */
function FoldIn({
  tag,
  onChoose,
}: {
  tag: TagPublic
  onChoose: (other: TagPublic) => void
}) {
  const { data: vocabulary } = useQuery(tagVocabularyQuery())
  const others = (vocabulary ?? []).filter((other) => other.id !== tag.id)

  if (vocabulary && others.length === 0) {
    return (
      <ReadOnlyValue>
        There is no other tag to fold into this one.
      </ReadOnlyValue>
    )
  }

  return (
    <span className="text-ink-2 flex flex-wrap items-center gap-x-1 text-sm">
      Fold another tag into this one:
      <Select
        // Always empty: choosing opens the confirmation, and the control is
        // ready for another choice if it is cancelled.
        value=""
        onValueChange={(id) => {
          const other = others.find((candidate) => candidate.id === id)
          if (other) onChoose(other)
        }}
      >
        <SelectTrigger
          aria-label="Choose a tag to fold in"
          disabled={!vocabulary}
          className={cn(
            quiet,
            "text-ink -ml-0 px-1.5 text-[13.5px] font-medium data-[placeholder]:text-ink",
          )}
        >
          <SelectValue placeholder="choose a tag…" />
        </SelectTrigger>
        <SelectContent>
          {others.map((other) => (
            <SelectItem key={other.id} value={other.id}>
              <span className="whitespace-pre">{other.name}</span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </span>
  )
}
