import { zodResolver } from "@hookform/resolvers/zod"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { useForm } from "react-hook-form"
import { z } from "zod"

import {
  AuthFailure,
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
import { EmailRefused, passkeysSupported, wasDismissed } from "@/lib/passkeys"

const formSchema = z.object({
  email: z.email({ message: "Invalid email address" }),
  // The same limit as the name in Settings.
  name: z.string().max(30, "The name is at most 30 characters"),
})

type FormData = z.infer<typeof formSchema>

export const Route = createFileRoute("/signup")({
  component: SignUp,
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
        title: "Create account - Taskly",
      },
    ],
  }),
})

function SignUp() {
  return (
    <AuthScreen
      heading="Create an account"
      lede="Your email names the account. The passkey your browser creates next is how you will sign in."
    >
      {passkeysSupported() ? <SignUpForm /> : <PasskeysUnsupported />}
      <AuthLinks>
        <AuthLink lead="Already have an account?" to="/login">
          Sign in
        </AuthLink>
      </AuthLinks>
    </AuthScreen>
  )
}

function SignUpForm() {
  const { registerMutation } = useAuth()
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: { email: "", name: "" },
  })

  const onSubmit = (data: FormData) => {
    if (registerMutation.isPending) return
    registerMutation.mutate(
      { email: data.email, name: data.name.trim() },
      {
        // A refused address is said under the email field, marked invalid,
        // and stays until the address is edited.
        onError: (error) => {
          if (error instanceof EmailRefused) {
            form.setError("email", { message: error.message })
          }
        },
      },
    )
  }

  // Any other failure is said under the action. A prompt the person
  // dismissed is not a problem to report.
  const failure =
    registerMutation.isError &&
    !(registerMutation.error instanceof EmailRefused) &&
    !wasDismissed(registerMutation.error)
      ? refusalMessage(registerMutation.error)
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
                    placeholder="user@example.com"
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
          name="name"
          render={({ field }) => (
            <FormItem className="gap-1">
              <FieldLine label="Name" htmlFor="name">
                <FormControl>
                  <input
                    id="name"
                    data-testid="name-input"
                    type="text"
                    autoComplete="name"
                    placeholder="Optional"
                    className={fieldInput}
                    {...field}
                  />
                </FormControl>
              </FieldLine>
              <FormMessage />
            </FormItem>
          )}
        />
        <p className="text-ink-3 mt-3 text-[13.5px] leading-normal">
          Taskly has no password. If you lose every passkey, the superuser can
          issue you a recovery code.
        </p>
        <LoadingButton
          type="submit"
          className={authAction}
          loading={registerMutation.isPending}
        >
          Create a passkey and sign in
        </LoadingButton>
        {failure && <AuthFailure>{failure}</AuthFailure>}
      </form>
    </Form>
  )
}
