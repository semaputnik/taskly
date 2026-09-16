// source: https://usehooks-ts.com/react-hook/use-copy-to-clipboard
import { useCallback, useState } from "react"

type CopiedValue = string | null

type CopyFn = (text: string) => Promise<boolean>

export function useCopyToClipboard(): [CopiedValue, CopyFn] {
  const [copiedText, setCopiedText] = useState<CopiedValue>(null)

  const copy: CopyFn = useCallback(async (text) => {
    try {
      // The Clipboard API exists only on secure origins, and can be refused
      // there; the editing command is still available either way.
      const written = await navigator.clipboard
        ?.writeText(text)
        .then(() => true)
        .catch(() => false)
      if (!written && !copyBySelection(text)) {
        console.warn("Copy failed: the clipboard refused it both ways")
        return false
      }
      setCopiedText(text)

      setTimeout(() => setCopiedText(null), 2000)

      return true
    } catch (error) {
      console.warn("Copy failed", error)
      setCopiedText(null)
      return false
    }
  }, [])

  return [copiedText, copy]
}

function copyBySelection(text: string): boolean {
  const field = document.createElement("textarea")
  field.value = text
  field.setAttribute("readonly", "")
  field.style.position = "fixed"
  field.style.opacity = "0"
  // Inside the open dialog, if there is one: a modal keeps focus from leaving.
  const previous = document.activeElement as HTMLElement | null
  const host = previous?.closest("[role=dialog]") ?? document.body
  host.appendChild(field)
  field.select()
  try {
    return document.execCommand("copy")
  } finally {
    field.remove()
    previous?.focus()
  }
}
