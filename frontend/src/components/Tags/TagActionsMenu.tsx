import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { TagPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import DeleteTag from "./DeleteTag"
import RenameTag from "./RenameTag"

export const TagActionsMenu = ({ tag }: { tag: TagPublic }) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Actions for ${tag.name}`}
        >
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <RenameTag tag={tag} onSuccess={() => setOpen(false)} />
        <DeleteTag tag={tag} onSuccess={() => setOpen(false)} />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
