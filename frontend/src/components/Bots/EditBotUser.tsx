import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Pencil } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"

import { BotsService, type BotUserPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { Form } from "@/components/ui/form"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import {
  type BotFormData,
  BotFormFields,
  botFormSchema,
  scopeProjectsQueryOptions,
  toBotScope,
} from "./BotFormFields"
import { PERMISSIONS } from "./permissions"

interface EditBotUserProps {
  bot: BotUserPublic
  onSuccess: () => void
}

function formValues(bot: BotUserPublic): BotFormData {
  return {
    name: bot.name,
    project_ids: bot.scope.project_ids,
    permissions: PERMISSIONS.filter(
      ({ key }) => bot.scope.permissions[key],
    ).map(({ key }) => key),
  }
}

/**
 * Renames a bot user and changes its scope. The token stays as it is, and the
 * bot user's next request is held to the new scope.
 */
const EditBotUser = ({ bot, onSuccess }: EditBotUserProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const { data: projects } = useQuery({
    ...scopeProjectsQueryOptions(),
    enabled: isOpen,
  })

  const form = useForm<BotFormData>({
    resolver: zodResolver(botFormSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: formValues(bot),
  })

  const mutation = useMutation({
    mutationFn: (data: BotFormData) =>
      BotsService.updateBotUser({
        path: { bot_user_id: bot.id },
        body: { name: data.name, scope: toBotScope(data) },
      }),
    onSuccess: () => {
      showSuccessToast("Bot updated successfully")
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["bots"] })
    },
  })

  const openDialog = (nextOpen: boolean) => {
    // Opened on what the bot user is now, not on an earlier, abandoned edit.
    if (nextOpen) {
      form.reset(formValues(bot))
    }
    setIsOpen(nextOpen)
  }

  return (
    <Dialog open={isOpen} onOpenChange={openDialog}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => openDialog(true)}
      >
        <Pencil />
        Edit Bot
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-md">
        <Form {...form}>
          <form onSubmit={form.handleSubmit((data) => mutation.mutate(data))}>
            <DialogHeader>
              <DialogTitle>Edit Bot</DialogTitle>
              <DialogDescription>
                Changes apply from the bot's next request. Its token stays as it
                is.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <BotFormFields
                form={form}
                projects={projects ?? []}
                archivedInScope={bot.scope.project_ids}
              />
            </div>

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  Cancel
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                Save
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default EditBotUser
