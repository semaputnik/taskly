import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"

import { BotsService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
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
import { useShowIssuedToken } from "./IssuedToken"
import { expiryFromDate, today } from "./tokens"

/**
 * Creates a bot user with its scope and issues its token straight away, so
 * the user leaves with a working credential in one go. Should issuing fail,
 * the bot user is still there and its row offers to issue the token again.
 */
const AddBotUser = () => {
  const [isOpen, setIsOpen] = useState(false)
  const showIssuedToken = useShowIssuedToken()
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const { data: projects } = useQuery({
    ...scopeProjectsQueryOptions(),
    enabled: isOpen,
  })

  const form = useForm<BotFormData>({
    resolver: zodResolver(botFormSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      name: "",
      project_ids: [],
      permissions: ["read_tasks"],
      token_expires_on: "",
    },
  })

  const mutation = useMutation({
    mutationFn: async (data: BotFormData) => {
      const { data: bot } = await BotsService.createBotUser({
        body: { name: data.name, scope: toBotScope(data) },
      })
      const { data: issuedToken } = await BotsService.issueBotUserToken({
        path: { bot_user_id: bot.id },
        body: { expires_at: expiryFromDate(data.token_expires_on) ?? null },
      })
      return {
        botName: bot.name,
        token: issuedToken.token,
        expiresAt: issuedToken.expires_at,
      }
    },
    onSuccess: (result) => {
      form.reset()
      setIsOpen(false)
      showIssuedToken(result)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["bots"] })
    },
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus />
          Add Bot
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Bot</DialogTitle>
          <DialogDescription>
            A bot user lets an integration work on your tasks through the REST
            API, only in the projects you pick and only in the ways you allow.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit((data) => mutation.mutate(data))}>
            <div className="grid gap-4 py-4">
              <BotFormFields form={form} projects={projects ?? []} />

              <FormField
                control={form.control}
                name="token_expires_on"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Token expires on (optional)</FormLabel>
                    <FormControl>
                      <Input type="date" min={today()} {...field} />
                    </FormControl>
                    <FormDescription>
                      Leave empty for a token that works until you revoke it.
                    </FormDescription>
                  </FormItem>
                )}
              />
            </div>

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  Cancel
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                Create and issue token
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default AddBotUser
