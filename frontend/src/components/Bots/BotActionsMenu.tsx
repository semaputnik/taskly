import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { BotUserPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import DeleteBotUser from "./DeleteBotUser"
import EditBotUser from "./EditBotUser"

export const BotActionsMenu = ({ bot }: { bot: BotUserPublic }) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Actions for ${bot.name}`}
        >
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditBotUser bot={bot} onSuccess={() => setOpen(false)} />
        <DeleteBotUser bot={bot} onSuccess={() => setOpen(false)} />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
