import { useMutation } from "@tanstack/react-query"
import { useForm } from "react-hook-form"

import { UsersService } from "@/client"
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
import { LoadingButton } from "@/components/ui/loading-button"
import useAuth from "@/hooks/useAuth"
import { useReportChange } from "@/lib/serverState"
import { toastError, toastSuccess } from "@/lib/toasts"

// What the confirming button says, and what the instruction above it names.
const CONFIRM = "Delete my account"

const DeleteConfirmation = () => {
  const reportChange = useReportChange()
  const { handleSubmit } = useForm()
  const { logout } = useAuth()

  const mutation = useMutation({
    mutationFn: () => UsersService.deleteUserMe(),
    onSuccess: () => {
      toastSuccess("Your account was deleted")
      logout()
    },
    onError: (error) => toastError(error),
    onSettled: () => reportChange({ type: "account changed" }),
  })

  const onSubmit = async () => {
    mutation.mutate()
  }

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="destructive" className="mt-3">
          Delete Account
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Delete your account?</DialogTitle>
            {/* The one act in the product with no way back at all: it says
                everything that goes, and names the button that does it. */}
            <DialogDescription>
              Everything in it is deleted with it: your tasks with their
              comments and files, your projects, your tags, your bot users and
              their live tokens, and your activity log. This cannot be undone.
              Press “{CONFIRM}” only if that is what you want.
            </DialogDescription>
          </DialogHeader>

          <DialogFooter className="mt-4">
            <DialogClose asChild>
              <Button variant="outline" disabled={mutation.isPending}>
                Cancel
              </Button>
            </DialogClose>
            <LoadingButton
              variant="destructive"
              type="submit"
              loading={mutation.isPending}
            >
              {CONFIRM}
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default DeleteConfirmation
