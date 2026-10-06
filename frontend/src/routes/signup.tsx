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
import { passkeysSupported } from "@/lib/passkeys"

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
    registerMutation.mutate({ email: data.email, name: data.name.trim() })
  }

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
        <LoadingButton
          type="submit"
          className={authAction}
          loading={registerMutation.isPending}
        >
          Create a passkey and sign in
        </LoadingButton>
      </form>
    </Form>
  )
}
