import { z } from "zod"

// As the API takes a tag's name: trimmed, then one to 50 characters.
export const tagNameSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, { message: "Name is required" })
    .max(50, { message: "Name can be at most 50 characters" }),
})

export type TagNameForm = z.infer<typeof tagNameSchema>
