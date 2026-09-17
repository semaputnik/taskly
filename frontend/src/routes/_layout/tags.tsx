import { usePrefetchQuery, useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Plus, Tag } from "lucide-react"
import { Suspense } from "react"

import { DataTable } from "@/components/Common/DataTable"
import { EmptyState } from "@/components/Common/EmptyState"
import PendingTags from "@/components/Pending/PendingTags"
import { useRecordPanels } from "@/components/Records/panels"
import { columns } from "@/components/Tags/columns"
import { DuplicateGroups } from "@/components/Tags/DuplicateGroups"
import { Button } from "@/components/ui/button"
import { tagDuplicatesQuery, tagsQuery } from "@/lib/serverState"

export const Route = createFileRoute("/_layout/tags")({
  component: Tags,
  head: () => ({
    meta: [
      {
        title: "Tags - Taskly",
      },
    ],
  }),
})

function TagsTableContent({
  onOpen,
  onAdd,
}: {
  onOpen: (tagId: string) => void
  onAdd: () => void
}) {
  const { data: tags } = useSuspenseQuery(tagsQuery())

  return (
    <DataTable
      columns={columns}
      data={tags.data}
      rowLabel={(tag) => `Open ${tag.name}`}
      onRowClick={(tag) => onOpen(tag.id)}
      empty={
        <EmptyState
          icon={Tag}
          title="No tags yet"
          description="Tags are created by using them: type one on a task and it appears here, ready to rename or reuse."
          action={<Button onClick={onAdd}>Add a tag</Button>}
        />
      }
    />
  )
}

/**
 * The user's tags, and the only place they are renamed or deleted
 * (FR-01.26). Creating one also happens by typing it onto a task.
 */
function Tags() {
  const { openTag, capture } = useRecordPanels()
  // Both requests start now, side by side, rather than one after the other as
  // each suspends in turn.
  usePrefetchQuery(tagsQuery())
  usePrefetchQuery(tagDuplicatesQuery())

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Tags</h1>
          <p className="text-muted-foreground">
            Label tasks across all of your projects
          </p>
        </div>
        <Button onClick={() => capture("tag")}>
          <Plus />
          Add Tag
        </Button>
      </div>
      <Suspense fallback={<PendingTags />}>
        <DuplicateGroups onOpenTag={openTag} />
        <TagsTableContent onOpen={openTag} onAdd={() => capture("tag")} />
      </Suspense>
    </div>
  )
}
