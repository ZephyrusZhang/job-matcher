"use client"

import { Suspense } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { LayoutList, Settings, Target } from "lucide-react"
import { Separator } from "@/components/ui/separator"
import { ThemeToggle } from "@/components/common/ThemeToggle"
import { ConversationList } from "@/components/match/ConversationList"
import { cn } from "@/lib/utils"

const navItems = [
  { href: "/jobs", label: "岗位总览", icon: LayoutList },
  { href: "/match", label: "智能匹配", icon: Target },
  // Settings is a destination like the other two, so it belongs in the nav
  // rather than being restyled as a footer entry.
  { href: "/settings", label: "设置", icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="hidden md:flex w-56 lg:w-56 md:w-48 flex-col border-r border-border-default bg-bg-secondary shrink-0">
      {/* Logo */}
      <div className="h-14 flex items-center justify-center shrink-0 border-b border-border-default">
        <span className="text-text-primary font-semibold text-base tracking-tight">
          JobMatcher
        </span>
      </div>

      {/* Primary navigation. Fixed height so the always-present conversation
          list below claims the remaining space. */}
      <nav className="flex shrink-0 flex-col gap-1 overflow-hidden px-3 py-3">
        {navItems.map((item) => {
          const isActive = pathname === item.href
          const Icon = item.icon
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-[var(--radius-sm)] text-sm transition-colors",
                isActive
                  ? "bg-[var(--nav-active-bg)] text-[var(--nav-active-fg)] font-medium"
                  : "text-text-secondary hover:bg-[var(--nav-hover-bg)] hover:text-text-primary",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span>{item.label}</span>
            </Link>
          )
        })}
      </nav>

      <Separator className="mx-3 mb-2 bg-border-default" />
      {/* ConversationList reads useSearchParams, and the sidebar renders on
          every route — without a boundary Next bails out of static rendering
          for all of them, including /404. */}
      <Suspense fallback={<div className="flex-1" />}>
        <ConversationList />
      </Suspense>

      {/* Footer: settings and theme share one row, mirroring the reference's
          two-action footer instead of stacking another full-width nav entry. */}
      {/* The theme switch is the only thing down here now, so it gets the row
          to itself. Sharing one with 设置 forced a flat nav entry and an
          animated capsule to be read as peers, which neither survived. */}
      <div className="flex shrink-0 justify-center border-t border-border-default px-3 py-3">
        <ThemeToggle />
      </div>
    </aside>
  )
}
