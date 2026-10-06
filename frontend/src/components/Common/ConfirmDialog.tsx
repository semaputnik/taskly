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
import { LoadingButton } from "@/components/ui/loading-button"

/**
 * The question an irreversible step asks first: what is about to be lost,
 * said before the button that does it. Webhooks and the Paperless connection
 * ask it the same way.
 */
export function ConfirmDialog({
  isOpen,
  onOpenChange,
  trigger,
  title,
  children,
  confirm,
  destructive = false,
  pending,
  onConfirm,
}: {
  isOpen: boolean
  onOpenChange: (open: boolean) => void
  trigger: React.ReactNode
  title: string
  children: React.ReactNode
  confirm: string
  destructive?: boolean
  pending: boolean
  onConfirm: () => void
}) {
  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      {trigger}
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{children}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={pending}>
              Cancel
            </Button>
          </DialogClose>
          <LoadingButton
            variant={destructive ? "destructive" : undefined}
            loading={pending}
            onClick={onConfirm}
          >
            {confirm}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
