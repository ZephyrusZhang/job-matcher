import { create } from "zustand"

/**
 * Light/dark theme store.
 *
 * Dark mode is the default (preserving the historical look). When the
 * user toggles to light mode, we:
 *   1. Add `className="light"` to <html>
 *   2. Persist the choice to localStorage under `jm-theme`
 *
 * To avoid a flash of wrong theme on first paint, an inline script in
 * layout.tsx reads localStorage *before* React hydrates and sets the
 * class synchronously.
 */

export type Theme = "light" | "dark"

const STORAGE_KEY = "jm-theme"

interface ThemeStore {
  theme: Theme
  setTheme: (theme: Theme) => void
  toggle: () => void
  /** Call once on client mount to sync state with the DOM class set by the inline boot script. */
  hydrate: () => void
}

function readStored(): Theme {
  if (typeof window === "undefined") return "dark"
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    return v === "light" ? "light" : "dark"
  } catch {
    return "dark"
  }
}

function applyToDom(theme: Theme) {
  if (typeof document === "undefined") return
  const root = document.documentElement
  if (theme === "light") {
    root.classList.add("light")
    root.classList.remove("dark")
  } else {
    root.classList.remove("light")
    root.classList.add("dark")
  }
}

export const useThemeStore = create<ThemeStore>((set, get) => ({
  theme: "dark",
  setTheme: (theme) => {
    set({ theme })
    applyToDom(theme)
    try {
      localStorage.setItem(STORAGE_KEY, theme)
    } catch {
      /* ignore (e.g. privacy mode) */
    }
  },
  toggle: () => {
    const next: Theme = get().theme === "dark" ? "light" : "dark"
    get().setTheme(next)
  },
  hydrate: () => {
    const stored = readStored()
    set({ theme: stored })
    applyToDom(stored)
  },
}))

/**
 * Inline script injected into <head> to set the theme class before
 * React hydrates. Returned as a string so it can be passed through
 * `dangerouslySetInnerHTML` without bundling.
 */
export const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem('${STORAGE_KEY}');var isLight=t==='light';var r=document.documentElement;if(isLight){r.classList.add('light');r.classList.remove('dark');}else{r.classList.add('dark');r.classList.remove('light');}}catch(e){document.documentElement.classList.add('dark');}})();`
