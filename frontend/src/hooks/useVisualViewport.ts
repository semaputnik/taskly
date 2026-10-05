import { useEffect } from "react"

/**
 * Publishes the visual viewport as two custom properties on the root, so a
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
 * Both are removed when the hook's user goes.
 */
export function useVisualViewport(enabled: boolean) {
  useEffect(() => {
    if (!enabled) return
    const viewport = window.visualViewport
    const root = document.documentElement
    const update = () => {
      const height = viewport?.height ?? window.innerHeight
      const top = viewport?.offsetTop ?? 0
      const inset = Math.max(0, window.innerHeight - (top + height))
      root.style.setProperty("--kb-inset", `${Math.round(inset)}px`)
      root.style.setProperty("--vv-height", `${Math.round(height)}px`)
    }
    update()
    viewport?.addEventListener("resize", update)
    viewport?.addEventListener("scroll", update)
    window.addEventListener("resize", update)
    return () => {
      viewport?.removeEventListener("resize", update)
      viewport?.removeEventListener("scroll", update)
      window.removeEventListener("resize", update)
      root.style.removeProperty("--kb-inset")
      root.style.removeProperty("--vv-height")
    }
  }, [enabled])
}
