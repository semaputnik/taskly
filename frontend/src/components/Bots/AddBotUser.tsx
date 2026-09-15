import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useId, useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { BotsService, type BotUserCreate, ProjectsService } from "@/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
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
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { useShowIssuedToken } from "./IssuedToken"
import { PERMISSIONS } from "./permissions"
import { expiryFromDate, today } from "./tokens"

const formSchema = z.object({
  name: z.string().trim().min(1, { message: "Name is required" }),
  project_ids: z.array(z.string()),
  permissions: z.array(z.string()),
  // A `yyyy-mm-dd`, or empty for a token that works until it is revoked.
  token_expires_on: z.string().optional(),
})

type FormData = z.infer<typeof formSchema>

function toBotUserCreate(data: FormData): BotUserCreate {
  return {
    name: data.name,
    scope: {
      project_ids: data.project_ids,
      permissions: Object.fromEntries(
        PERMISSIONS.map(({ key }) => [key, data.permissions.includes(key)]),
      ),
    },
  }
}

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
    queryFn: async () =>
      (await ProjectsService.readProjects({ query: { skip: 0, limit: 100 } }))
        .data,
    queryKey: ["projects"],
    enabled: isOpen,
  })

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
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
    mutationFn: async (data: FormData) => {
      const { data: bot } = await BotsService.createBotUser({
        body: toBotUserCreate(data),
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
        <Button className="my-4">
          <Plus className="mr-2" />
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
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Name <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="Bot name" type="text" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="project_ids"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Projects</FormLabel>
                    <FormDescription>
                      Each project is picked on its own: a project you create
                      later is never added by itself.
                    </FormDescription>
                    <div className="flex flex-col gap-2">
                      {projects?.data.map((project) => (
                        <CheckboxRow
                          key={project.id}
                          label={project.name}
                          checked={field.value.includes(project.id)}
                          onCheckedChange={(checked) =>
                            field.onChange(
                              checked
                                ? [...field.value, project.id]
                                : field.value.filter((id) => id !== project.id),
                            )
                          }
                        />
                      ))}
                    </div>
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="permissions"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Permissions</FormLabel>
                    <div className="flex flex-col gap-2">
                      {PERMISSIONS.map(({ key, label }) => (
                        <CheckboxRow
                          key={key}
                          label={label}
                          checked={field.value.includes(key)}
                          onCheckedChange={(checked) =>
                            field.onChange(
                              checked
                                ? [...field.value, key]
                                : field.value.filter((value) => value !== key),
                            )
                          }
                        />
                      ))}
                    </div>
                  </FormItem>
                )}
              />

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

interface CheckboxRowProps {
  label: string
  checked: boolean
  onCheckedChange: (checked: boolean) => void
}

const CheckboxRow = ({ label, checked, onCheckedChange }: CheckboxRowProps) => {
  const id = useId()
  return (
    <div className="flex items-center gap-2">
      <Checkbox
        id={id}
        checked={checked}
        onCheckedChange={(value) => onCheckedChange(value === true)}
      />
      <Label htmlFor={id} className="font-normal">
        {label}
      </Label>
    </div>
  )
}

export default AddBotUser
