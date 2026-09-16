import { toast } from "sonner"

/**
 * Notices for the outcome of an act. The message is the notice: severity is
 * carried by the icon beside it, never by a generic heading such as
 * "Success!" above the words that actually say what happened.
 */
const useCustomToast = () => {
  const showSuccessToast = (message: string) => {
    toast.success(message)
  }

  const showErrorToast = (message: string) => {
    toast.error(message)
  }

  return { showSuccessToast, showErrorToast }
}

export default useCustomToast
