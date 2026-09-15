import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Tag } from "lucide-react"
import { Suspense } from "react"

import { TagsService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { EmptyState } from "@/components/Common/EmptyState"
import PendingTags from "@/components/Pending/PendingTags"
import AddTag from "@/components/Tags/AddTag"
import { columns } from "@/components/Tags/columns"

// Under "tags", so creating, renaming and deleting refresh autocomplete and the
// tag filter along with this page.
function getTagsQueryOptions() {
  const query = { skip: 0, limit: 100 }
  return {
    queryFn: async () => (await TagsService.readTags({ query })).data,
    queryKey: ["tags", "all", query],
  }
}

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

function TagsTableContent() {
  const { data: tags } = useSuspenseQuery(getTagsQueryOptions())

  return (
    <DataTable
      columns={columns}
      data={tags.data}
      empty={
        <EmptyState
          icon={Tag}
          title="No tags yet"
          description="Tags are created by using them: type one on a task and it appears here, ready to rename or reuse."
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
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Tags</h1>
          <p className="text-muted-foreground">
            Label tasks across all of your projects
          </p>
        </div>
        <AddTag />
      </div>
      <Suspense fallback={<PendingTags />}>
        <TagsTableContent />
      </Suspense>
    </div>
  )
}
