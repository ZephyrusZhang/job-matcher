"use client"

import { useEffect, useState } from "react"
import { cn } from "@/lib/utils"
import { useThemeStore } from "@/lib/theme"

interface ThemeToggleProps {
  /** Extra classes for positioning/spacing. */
  className?: string
}

/**
 * Celestial theme switch.
 *
 * A track-style toggle with a sun-to-moon sliding thumb, radiating
 * rays, drifting clouds (light mode) and twinkling stars (dark mode).
 * All motion is pure CSS via classes defined in globals.css, so the
 * component stays small and zero-JS during animation.
 *
 * The keyframe-driven decorations (`.twinkle`, `.drift`) auto-play;
 * clicking the button flips the `.theme-switch--dark` class which
 * drives a spring-eased thumb slide + color morph.
 */
export function ThemeToggle({ className }: ThemeToggleProps) {
  const theme = useThemeStore((s) => s.theme)
  const toggle = useThemeStore((s) => s.toggle)
  const hydrate = useThemeStore((s) => s.hydrate)
  const [isPressed, setIsPressed] = useState(false)

  useEffect(() => {
    hydrate()
  }, [hydrate])

  const isDark = theme === "dark"
  const label = isDark ? "切换为亮色模式" : "切换为暗色模式"

  const handleClick = () => {
    setIsPressed(true)
    toggle()
    // squash timer – matches the 600ms spring transition in CSS
    window.setTimeout(() => setIsPressed(false), 600)
  }

  return (
    <button
      type="button"
      role="switch"
      aria-checked={!isDark}
      aria-label={label}
      title={label}
      onClick={handleClick}
      className={cn(
        "theme-switch group",
        isDark ? "theme-switch--dark" : "theme-switch--light",
        isPressed && "theme-switch--pressed",
        className,
      )}
    >
      {/* Track backdrop layers (gradient + glow) */}
      <span className="theme-switch__track" aria-hidden />
      <span className="theme-switch__glow" aria-hidden />

      {/* Twinkling stars — visible only in dark mode */}
      <span className="theme-switch__star theme-switch__star--1" aria-hidden />
      <span className="theme-switch__star theme-switch__star--2" aria-hidden />
      <span className="theme-switch__star theme-switch__star--3" aria-hidden />
      <span className="theme-switch__star theme-switch__star--4" aria-hidden />

      {/* Drifting clouds — visible only in light mode */}
      <span className="theme-switch__cloud theme-switch__cloud--1" aria-hidden />
      <span className="theme-switch__cloud theme-switch__cloud--2" aria-hidden />

      {/* Sliding thumb — outer layer handles translateX slide */}
      <span className="theme-switch__thumb" aria-hidden>
        {/* Inner layer handles squash scale independently to avoid
            clobbering the outer translateX transition. */}
        <span className="theme-switch__thumb-inner">
          {/* Sun rays (rotate out when light) */}
          <span className="theme-switch__rays">
            {Array.from({ length: 8 }).map((_, i) => (
              <span
                key={i}
                className="theme-switch__ray"
                style={{ transform: `rotate(${i * 45}deg) translateY(-11px)` }}
              />
            ))}
          </span>
          {/* Sun / moon body — the moon is the sun with a dark crescent overlaid */}
          <span className="theme-switch__body">
            <span className="theme-switch__crescent" />
            <span className="theme-switch__crater theme-switch__crater--1" />
            <span className="theme-switch__crater theme-switch__crater--2" />
            <span className="theme-switch__crater theme-switch__crater--3" />
          </span>
        </span>
      </span>
    </button>
  )
}
