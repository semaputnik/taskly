import { useId } from "react"
import type { UseFormReturn } from "react-hook-form"
import { z } from "zod"

import type { BotScope } from "@/client"
import { Checkbox } from "@/components/ui/checkbox"
import {
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { ScopeProject } from "@/lib/serverState"
import { PERMISSIONS } from "./permissions"

export const botFormSchema = z.object({
  name: z.string().trim().min(1, { message: "Name is required" }),
  project_ids: z.array(z.string()),
  permissions: z.array(z.string()),
  // A `yyyy-mm-dd`, or empty for a token that works until it is revoked. Only
  // creating a bot user issues a token, so only that form sets it.
  token_expires_on: z.string().optional(),
})

export type BotFormData = z.infer<typeof botFormSchema>

export function toBotScope(data: BotFormData): BotScope {
  return {
    project_ids: data.project_ids,
    permissions: Object.fromEntries(
      PERMISSIONS.map(({ key }) => [key, data.permissions.includes(key)]),
    ),
  }
}

interface BotFormFieldsProps {
  form: UseFormReturn<BotFormData>
  projects: ScopeProject[]
  /**
   * Archived projects already in the scope being edited. They are offered so
   * they can be taken out; no other archived project is, since a bot user
   * reaches nothing archived whatever its scope says.
   */
  archivedInScope?: string[]
}

/** The name and scope of a bot user, as creating and editing both ask. */
export const BotFormFields = ({
  form,
  projects,
  archivedInScope = [],
}: BotFormFieldsProps) => {
  const offered = projects.filter(
    (project) => !project.archived || archivedInScope.includes(project.id),
  )

  return (
    <>
      <FormField
        control={form.control}
        name="name"
        render={({ field }) => (
          <FormItem>
            <FormLabel>
              Name <span className="text-destructive">*</span>
            </FormLabel>
            <FormControl>
              <Input placeholder="Bot name" type="text" {...field} />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={form.control}
        name="project_ids"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Projects</FormLabel>
            <FormDescription>
              Each project is picked on its own: a project you create later is
              never added by itself.
            </FormDescription>
            <div className="flex flex-col gap-2">
              {offered.map((project) => (
                <CheckboxRow
                  key={project.id}
                  label={
                    project.archived
                      ? `${project.name} (archived)`
                      : project.name
                  }
                  checked={field.value.includes(project.id)}
                  onCheckedChange={(checked) =>
                    field.onChange(
                      checked
                        ? [...field.value, project.id]
                        : field.value.filter((id) => id !== project.id),
                    )
                  }
                />
              ))}
            </div>
          </FormItem>
        )}
      />

      <FormField
        control={form.control}
        name="permissions"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Permissions</FormLabel>
            <div className="flex flex-col gap-2">
              {PERMISSIONS.map(({ key, label }) => (
                <CheckboxRow
                  key={key}
                  label={label}
                  checked={field.value.includes(key)}
                  onCheckedChange={(checked) =>
                    field.onChange(
                      checked
                        ? [...field.value, key]
                        : field.value.filter((value) => value !== key),
                    )
                  }
                />
              ))}
            </div>
          </FormItem>
        )}
      />
    </>
  )
}

interface CheckboxRowProps {
  label: string
  checked: boolean
  onCheckedChange: (checked: boolean) => void
}

const CheckboxRow = ({ label, checked, onCheckedChange }: CheckboxRowProps) => {
  const id = useId()
  return (
    <div className="flex items-center gap-2">
      <Checkbox
        id={id}
        checked={checked}
        onCheckedChange={(value) => onCheckedChange(value === true)}
      />
      <Label htmlFor={id} className="font-normal">
        {label}
      </Label>
    </div>
  )
}
