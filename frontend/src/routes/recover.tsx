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
    <AuthLayout>
      <div className="flex flex-col gap-6">
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="text-2xl font-bold">Recover your account</h1>
          <p className="text-muted-foreground text-sm">
            Lost every passkey? Ask the person who runs this Taskly for a
            recovery code, then make a new passkey with it here.
          </p>
        </div>
        {passkeysSupported() ? <RecoverForm /> : <PasskeysUnsupported />}
      </div>
    </AuthLayout>
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
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="code"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Recovery code</FormLabel>
                <FormControl>
                  <Input
                    data-testid="recovery-code-input"
                    placeholder="XXXX-XXXX-XXXX-XXXX"
                    autoComplete="one-time-code"
                    spellCheck={false}
                    className="font-mono"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <LoadingButton
            type="submit"
            className="w-full"
            loading={recoverMutation.isPending}
          >
            Create a new passkey
          </LoadingButton>
        </div>

        <div className="text-center text-sm">
          <RouterLink to="/login" className="underline underline-offset-4">
            Back to sign in
          </RouterLink>
        </div>
      </form>
    </Form>
  )
}
