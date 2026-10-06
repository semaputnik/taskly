import { type RefObject, useEffect } from "react"

/**
 * Publishes the visual viewport as two custom properties on `target`, so a
 * bar pinned to the bottom of the screen can follow it without re-rendering:
 *
 * - `--kb-inset`: how far the bottom of what is seen sits above the bottom of
 *   the layout viewport. Zero at rest; the height of the keyboard while one is
 *   up, since iOS Safari leaves the layout viewport behind the keyboard and
 *   shrinks only the visual one (and moves its top when it scrolls the page
 *   to keep a field in view).
 * - `--vv-height`: the height of what is seen, which bounds anything that
 *   opens above the bar.
 *
 * They are set on the bar rather than the root: a custom property inherits,
 * so one changed on the root restyles the whole page, and while a keyboard
 * is up it changes on every frame the page scrolls. The events of one frame
 * are written once, before that frame is drawn.
 *
 * Both are removed when the hook's user goes.
 */
export function useVisualViewport(
  target: RefObject<HTMLElement | null>,
  enabled: boolean,
) {
  useEffect(() => {
    const element = target.current
    if (!enabled || !element) return
    const viewport = window.visualViewport
    const write = () => {
      const height = viewport?.height ?? window.innerHeight
      const top = viewport?.offsetTop ?? 0
      const inset = Math.max(0, window.innerHeight - (top + height))
      element.style.setProperty("--kb-inset", `${Math.round(inset)}px`)
      element.style.setProperty("--vv-height", `${Math.round(height)}px`)
    }
    let frame = 0
    const update = () => {
      if (frame) return
      frame = requestAnimationFrame(() => {
        frame = 0
        write()
      })
    }
    write()
    viewport?.addEventListener("resize", update)
    viewport?.addEventListener("scroll", update)
    window.addEventListener("resize", update)
    return () => {
      cancelAnimationFrame(frame)
      viewport?.removeEventListener("resize", update)
      viewport?.removeEventListener("scroll", update)
      window.removeEventListener("resize", update)
      element.style.removeProperty("--kb-inset")
      element.style.removeProperty("--vv-height")
    }
  }, [target, enabled])
}
