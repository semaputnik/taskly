import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Pencil } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"

import { type TagPublic, TagsService } from "@/client"
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
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { type TagNameForm, tagNameSchema } from "./tagName"

interface RenameTagProps {
  tag: TagPublic
  onSuccess: () => void
}

/** Renames a tag on every task that carries it (FR-01.24). */
const RenameTag = ({ tag, onSuccess }: RenameTagProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<TagNameForm>({
    resolver: zodResolver(tagNameSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: { name: tag.name },
  })

  const mutation = useMutation({
    mutationFn: (data: TagNameForm) =>
      TagsService.renameTag({ path: { tag_id: tag.id }, body: data }),
    onSuccess: () => {
      showSuccessToast("Tag renamed successfully")
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tags"] })
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
    },
  })

  const openDialog = (nextOpen: boolean) => {
    if (nextOpen) {
      form.reset({ name: tag.name })
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
        Rename Tag
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-md">
        <Form {...form}>
          <form onSubmit={form.handleSubmit((data) => mutation.mutate(data))}>
            <DialogHeader>
              <DialogTitle>Rename Tag</DialogTitle>
              <DialogDescription>
                Every task tagged “{tag.name}” shows the new name.
              </DialogDescription>
            </DialogHeader>
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
                      <Input placeholder="Tag name" type="text" {...field} />
                    </FormControl>
                    <FormMessage />
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
                Save
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default RenameTag
