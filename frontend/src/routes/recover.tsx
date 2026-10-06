import { zodResolver } from "@hookform/resolvers/zod"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { useForm } from "react-hook-form"
import { z } from "zod"

import {
  AuthLink,
  AuthLinks,
  AuthScreen,
  authAction,
  FieldLine,
  fieldInput,
  PasskeysUnsupported,
} from "@/components/Auth/AuthScreen"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from "@/components/ui/form"
import { LoadingButton } from "@/components/ui/loading-button"
import useAuth, { isLoggedIn } from "@/hooks/useAuth"
import { refusalMessage } from "@/lib/apiErrors"
import { passkeysSupported, wasDismissed } from "@/lib/passkeys"

const formSchema = z.object({
  email: z.email({ message: "Invalid email address" }),
  code: z.string().trim().min(1, { message: "Enter the recovery code" }),
})

type FormData = z.infer<typeof formSchema>

export const Route = createFileRoute("/recover")({
  component: Recover,
  beforeLoad: async () => {
    if (isLoggedIn()) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Recover your account - Taskly",
      },
    ],
  }),
})

function Recover() {
  return (
    <AuthScreen
      heading="Recover your account"
      lede="Enter the code the superuser gave you. It creates a new passkey and signs you out everywhere else."
    >
      {passkeysSupported() ? <RecoverForm /> : <PasskeysUnsupported />}
      <AuthLinks>
        <AuthLink to="/login">Back to sign in</AuthLink>
      </AuthLinks>
    </AuthScreen>
  )
}

function RecoverForm() {
  const { recoverMutation } = useAuth()
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: { email: "", code: "" },
  })

  const onSubmit = (data: FormData) => {
    if (recoverMutation.isPending) return
    recoverMutation.mutate(data)
  }

  // A refusal is said here, beside the code that was refused, in the API's
  // words: a wrong code, a spent one and an expired one read the same
  // (FR-12.18). A prompt the person dismissed is not a problem to report.
  const refusal =
    recoverMutation.isError && !wasDismissed(recoverMutation.error)
      ? refusalMessage(recoverMutation.error)
      : null

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col">
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem className="gap-1">
              <FieldLine label="Email" htmlFor="email">
                <FormControl>
                  <input
                    id="email"
                    data-testid="email-input"
                    type="email"
                    autoComplete="username"
                    className={fieldInput}
                    {...field}
                  />
                </FormControl>
              </FieldLine>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="code"
          render={({ field }) => (
            <FormItem className="gap-1">
              <FieldLine label="Code" htmlFor="code">
                <FormControl>
                  <input
                    id="code"
                    data-testid="recovery-code-input"
                    placeholder="XXXX-XXXX-XXXX-XXXX"
                    autoComplete="one-time-code"
                    spellCheck={false}
                    className={`${fieldInput} font-mono tracking-[0.12em]`}
                    {...field}
                  />
                </FormControl>
              </FieldLine>
              <FormMessage />
            </FormItem>
          )}
        />
        {refusal && (
          <p role="alert" className="text-late mt-3 text-[13.5px] font-medium">
            {refusal}
          </p>
        )}
        <LoadingButton
          type="submit"
          className={authAction}
          loading={recoverMutation.isPending}
        >
          Create a new passkey
        </LoadingButton>
      </form>
    </Form>
  )
}
