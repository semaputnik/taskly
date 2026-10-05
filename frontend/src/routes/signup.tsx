import { zodResolver } from "@hookform/resolvers/zod"
import {
  createFileRoute,
  Link as RouterLink,
  redirect,
} from "@tanstack/react-router"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { AuthLayout } from "@/components/Common/AuthLayout"
import { PasskeysUnsupported } from "@/components/Common/PasskeysUnsupported"
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
import { LoadingButton } from "@/components/ui/loading-button"
import useAuth, { isLoggedIn } from "@/hooks/useAuth"
import { passkeysSupported } from "@/lib/passkeys"

const formSchema = z.object({
  email: z.email({ message: "Invalid email address" }),
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
    <AuthLayout>
      <div className="flex flex-col gap-6">
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="text-2xl font-bold">Create an account</h1>
        </div>
        {passkeysSupported() ? <SignUpForm /> : <PasskeysUnsupported />}
      </div>
    </AuthLayout>
  )
}

function SignUpForm() {
  const { registerMutation } = useAuth()
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: { email: "" },
  })

  const onSubmit = (data: FormData) => {
    if (registerMutation.isPending) return
    registerMutation.mutate(data.email)
  }

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        className="flex flex-col gap-6"
      >
        <div className="grid gap-4">
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Email</FormLabel>
                <FormControl>
                  <Input
                    data-testid="email-input"
                    placeholder="user@example.com"
                    type="email"
                    autoComplete="username"
                    {...field}
                  />
                </FormControl>
                <FormDescription>
                  Your device then makes a passkey for this account. It is how
                  you sign in from now on; there is no password.
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          <LoadingButton
            type="submit"
            className="w-full"
            loading={registerMutation.isPending}
          >
            Create account
          </LoadingButton>
        </div>

        <div className="text-center text-sm">
          Already have an account?{" "}
          <RouterLink to="/login" className="underline underline-offset-4">
            Sign in
          </RouterLink>
        </div>
      </form>
    </Form>
  )
}
