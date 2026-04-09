"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { LayoutList, Target, BarChart3, Settings } from "lucide-react"
import { Separator } from "@/components/ui/separator"
import { ThemeToggle } from "@/components/common/ThemeToggle"
import { cn } from "@/lib/utils"

const navItems = [
  { href: "/jobs", label: "岗位总览", icon: LayoutList },
  { href: "/match", label: "智能匹配", icon: Target },
  { href: "/compare", label: "岗位对比", icon: BarChart3 },
]

const bottomItems = [
  { href: "/settings", label: "设置", icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="hidden md:flex w-56 lg:w-56 md:w-48 flex-col border-r border-border-default bg-bg-secondary shrink-0">
      {/* Logo */}
      <div className="h-14 flex items-center justify-center shrink-0 border-b border-border-default">
        <span className="text-text-primary font-semibold text-base tracking-tight">JobMatcher</span>
      </div>

      <nav className="flex-1 flex flex-col px-3 py-3 gap-2 overflow-hidden">
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
                  : "text-text-secondary hover:bg-[var(--nav-hover-bg)] hover:text-text-primary"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span>{item.label}</span>
            </Link>
          )
        })}

        <Separator className="my-2 bg-border-default" />

        {bottomItems.map((item) => {
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
                  : "text-text-secondary hover:bg-[var(--nav-hover-bg)] hover:text-text-primary"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span>{item.label}</span>
            </Link>
          )
        })}
      </nav>

      {/* Theme switch — pinned to the bottom of the sidebar, centered. */}
      <div className="shrink-0 border-t border-border-default py-4 flex items-center justify-center">
        <ThemeToggle />
      </div>
    </aside>
  )
}
