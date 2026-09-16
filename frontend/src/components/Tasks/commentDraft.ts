import { useRef, useState } from "react"

interface Draft {
  text: string
  /** Where the caret was, so typing picks up where it stopped. */
  caret: number
}

// Unsent comments, by task. The thread is unmounted whenever its tab is not
// the one on screen — that is what keeps the other tabs from fetching — so a
// draft kept in the thread would go with it. Held here, a half-written note
// survives a look at the subtasks, a visit to one of them, and closing the
// panel, for as long as the page is open.
const drafts = new Map<string, Draft>()

/**
 * The comment being written on a task, kept across everything that unmounts
 * the thread. Spread `field` onto the textarea.
 */
export function useCommentDraft(taskId: string) {
  const [text, setText] = useState(() => drafts.get(taskId)?.text ?? "")
  // A click places the caret itself; only focus that arrives some other way
  // — Tab, or the field coming back — is sent to where the reader left off.
  const pointing = useRef(false)

  const remember = (next: string, caret: number) => {
    if (next) drafts.set(taskId, { text: next, caret })
    else drafts.delete(taskId)
  }

  return {
    text,
    clear: () => {
      drafts.delete(taskId)
      setText("")
    },
    field: {
      value: text,
      onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        remember(e.target.value, e.target.selectionEnd)
        setText(e.target.value)
      },
      onSelect: (e: React.SyntheticEvent<HTMLTextAreaElement>) =>
        remember(e.currentTarget.value, e.currentTarget.selectionEnd),
      onPointerDown: () => {
        pointing.current = true
      },
      onFocus: (e: React.FocusEvent<HTMLTextAreaElement>) => {
        const saved = drafts.get(taskId)
        if (saved && !pointing.current) {
          e.currentTarget.setSelectionRange(saved.caret, saved.caret)
        }
        pointing.current = false
      },
    },
  }
}
