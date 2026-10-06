import { useMutation } from "@tanstack/react-query"
import { useId, useState } from "react"
import { z } from "zod"

import { UsersService, type UserUpdateMe } from "@/client"
import { PropertyRow } from "@/components/Records/RecordPanel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useAuth from "@/hooks/useAuth"
import { useReportChange } from "@/lib/serverState"
import { toastError, toastSuccess } from "@/lib/toasts"
import { Appearance } from "./Appearance"
import { act, SettingsSection } from "./Section"

const nameSchema = z.string().max(30, "The name is at most 30 characters")
const emailSchema = z.email({ message: "Invalid email address" })

/**
 * Who the reader is: the name and the email, each said as a value with
 * Change beside it (FR-09.4), and how the page looks. Change turns the value
 * into its field in place; Save sends that one field and puts the value back.
 */
export function Profile() {
  const { user } = useAuth()
  if (!user) return null

  return (
    <SettingsSection id="profile" title="Profile">
      <div className="flex flex-col gap-0.5">
        <Field
          label="Name"
          value={user.full_name ?? ""}
          empty="Not set"
          schema={nameSchema}
          type="text"
          toBody={(full_name) => ({ full_name })}
        />
        <Field
          label="Email"
          value={user.email}
          schema={emailSchema}
          type="email"
          toBody={(email) => ({ email })}
        />
        <Appearance />
      </div>
    </SettingsSection>
  )
}

function Field({
  label,
  value,
  empty,
  schema,
  type,
  toBody,
}: {
  label: string
  value: string
  /** What an empty value says, in words. */
  empty?: string
  schema: z.ZodType<string>
  type: "text" | "email"
  toBody: (next: string) => UserUpdateMe
}) {
  const reportChange = useReportChange()
  const id = useId()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const [problem, setProblem] = useState<string | null>(null)

  const check = (next: string) => {
    const result = schema.safeParse(next)
    setProblem(result.success ? null : result.error.issues[0].message)
    return result.success
  }

  const save = useMutation({
    mutationFn: (next: string) =>
      UsersService.updateUserMe({ body: toBody(next) }),
    onSuccess: () => {
      toastSuccess("User updated successfully")
      setEditing(false)
    },
    onError: (error) => toastError(error),
    onSettled: () => reportChange({ type: "account changed" }),
  })

  const open = () => {
    setDraft(value)
    setProblem(null)
    setEditing(true)
  }
  const close = () => {
    setProblem(null)
    setEditing(false)
  }
  const submit = () => {
    if (!check(draft)) return
    if (draft === value) return close()
    save.mutate(draft)
  }

  return (
    <PropertyRow label={label} htmlFor={editing ? id : undefined}>
      {editing ? (
        <form
          className="flex min-w-0 flex-1 flex-wrap items-start gap-x-3 gap-y-1"
          onSubmit={(event) => {
            event.preventDefault()
            submit()
          }}
        >
          <div className="flex min-w-0 flex-1 basis-56 flex-col gap-1">
            <Input
              id={id}
              type={type}
              value={draft}
              autoFocus
              aria-invalid={problem !== null}
              aria-describedby={problem ? `${id}-problem` : undefined}
              className="h-[30px] md:text-sm"
              onChange={(event) => setDraft(event.target.value)}
              onBlur={() => check(draft)}
              onKeyDown={(event) => {
                if (event.key === "Escape") close()
              }}
            />
            {problem && (
              <p
                id={`${id}-problem`}
                role="alert"
                className="text-late text-[12.5px]"
              >
                {problem}
              </p>
            )}
          </div>
          <div className="flex h-[30px] items-center gap-3 pointer-coarse:h-11">
            <LoadingButton type="submit" size="sm" loading={save.isPending}>
              Save
            </LoadingButton>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={save.isPending}
              onClick={close}
            >
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <>
          {value ? (
            <span className="text-ink min-w-0 truncate text-sm">{value}</span>
          ) : (
            <span className="text-ink-3 text-sm italic">{empty}</span>
          )}
          <button type="button" className={act} onClick={open}>
            Change
            <span className="sr-only"> {label.toLowerCase()}</span>
          </button>
        </>
      )}
    </PropertyRow>
  )
}
