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
      {/* Padding and inner spacing match the nav above so the 设置 icon lands
          on the same vertical line as 岗位总览 / 智能匹配 — it is the same kind
          of entry, just parked at the bottom. */}
      <div className="shrink-0 border-t border-border-default px-3 py-2">
        <div className="flex items-center gap-2">
          <Link
            href="/settings"
            className={cn(
              "flex min-w-0 flex-1 items-center gap-3 rounded-[var(--radius-sm)] px-3 py-2 text-sm transition-colors",
              pathname === "/settings"
                ? "bg-[var(--nav-active-bg)] text-[var(--nav-active-fg)] font-medium"
                : "text-text-secondary hover:bg-[var(--nav-hover-bg)] hover:text-text-primary",
            )}
          >
            <Settings className="h-4 w-4 shrink-0" />
            <span className="truncate">设置</span>
          </Link>
          {/* Boxed to the nav row's height so the two sit on one baseline
              rather than the shorter switch floating beside a taller pill. */}
          <div className="flex h-9 shrink-0 items-center">
            <ThemeToggle />
          </div>
        </div>
      </div>
    </aside>
  )
}
