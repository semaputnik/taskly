"use client"

import {
  CircleCheckIcon,
  InfoIcon,
  Loader2Icon,
  OctagonXIcon,
  TriangleAlertIcon,
} from "lucide-react"
import { useTheme } from "@/components/theme-provider"
import { Toaster as Sonner, type ToasterProps } from "sonner"

/**
 * Where every notice appears: the top of the screen, centred on a desktop,
 * the full width between 16px gutters on a phone. The safe area keeps one
 * clear of a notch.
 */
const TOP = "calc(12px + env(safe-area-inset-top))"
const PLACE = {
  position: "top-center",
  offset: { top: TOP },
  mobileOffset: { top: TOP, left: "16px", right: "16px" },
} satisfies ToasterProps

const textAction =
  "h-auto! bg-transparent! px-1! py-1! text-[13.5px]! font-medium! text-ink! underline-offset-4 hover:underline pointer-coarse:h-11! pointer-coarse:px-4!"

/**
 * A notice is a line of the log that has left the page, so it is the page
 * itself — ground, hairline, a real shadow for the height it has gained —
 * and its actions are text. Severity is the icon's colour and never a
 * filled ground: colour is for state that asks for action.
 */
const classNames = {
  toast:
    "gap-3! rounded-lg! px-3.5! py-2! text-[13.5px]! shadow-[0_10px_24px_-8px_rgb(0_0_0/0.25),0_2px_6px_rgb(0_0_0/0.08)]! dark:shadow-[0_10px_24px_-8px_rgb(0_0_0/0.7),0_2px_6px_rgb(0_0_0/0.4)]!",
  content: "flex-1",
  success: "[&_[data-icon]]:text-done",
  error: "[&_[data-icon]]:text-late",
  actionButton: textAction,
  cancelButton: textAction,
}

const Toaster = ({ toastOptions, style, ...props }: ToasterProps) => {
  const { theme } = useTheme()

  return (
    <Sonner
      theme={theme}
      className="toaster group"
      {...PLACE}
      icons={{
        success: <CircleCheckIcon className="size-4" />,
        info: <InfoIcon className="size-4" />,
        warning: <TriangleAlertIcon className="size-4" />,
        error: <OctagonXIcon className="size-4" />,
        loading: <Loader2Icon className="size-4 animate-spin" />,
      }}
      toastOptions={{
        ...toastOptions,
        classNames: { ...classNames, ...toastOptions?.classNames },
      }}
      style={
        {
          "--normal-bg": "var(--page)",
          "--normal-text": "var(--ink)",
          "--normal-border": "var(--rule-strong)",
          "--border-radius": "var(--radius)",
          "--width": "min(420px, calc(100vw - 32px))",
          ...style,
        } as React.CSSProperties
      }
      {...props}
    />
  )
}

export { Toaster }
