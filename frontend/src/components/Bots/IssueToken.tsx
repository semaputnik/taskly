import { useMutation, useQueryClient } from "@tanstack/react-query"
import { KeyRound } from "lucide-react"
import { useState } from "react"

import { BotsService, type BotUserPublic } from "@/client"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import TokenDialog from "./TokenDialog"

const IssueToken = ({ bot }: { bot: BotUserPublic }) => {
  const [token, setToken] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () =>
      BotsService.issueBotUserToken({ path: { bot_user_id: bot.id } }),
    onSuccess: ({ data }) => setToken(data.token),
    onError: (error) => {
      handleError.call(showErrorToast, error)
      queryClient.invalidateQueries({ queryKey: ["bots"] })
    },
  })

  // The row this button sits in stops offering it once the list knows a
  // token is out, so the list is only refreshed after the token has been
  // seen: refreshing sooner would take the dialog down with the button.
  const close = () => {
    setToken(null)
    queryClient.invalidateQueries({ queryKey: ["bots"] })
  }

  return (
    <>
      <LoadingButton
        variant="outline"
        size="sm"
        loading={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        <KeyRound />
        Issue token
      </LoadingButton>
      <TokenDialog botName={bot.name} token={token} onClose={close} />
    </>
  )
}

export default IssueToken
