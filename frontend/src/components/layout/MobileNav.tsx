"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { LayoutList, Target, BarChart3, Settings } from "lucide-react"
import { cn } from "@/lib/utils"

const navItems = [
  { href: "/jobs", label: "岗位", icon: LayoutList },
  { href: "/match", label: "匹配", icon: Target },
  { href: "/compare", label: "对比", icon: BarChart3 },
  { href: "/settings", label: "设置", icon: Settings },
]

export function MobileNav() {
  const pathname = usePathname()

  return (
    <nav className="md:hidden flex items-center border-b border-border-default bg-bg-secondary shrink-0">
      <span className="text-text-primary font-semibold text-sm px-4 shrink-0">JM</span>
      <div className="flex flex-1 overflow-x-auto">
        {navItems.map((item) => {
          const isActive = pathname === item.href
          const Icon = item.icon
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-1.5 px-3 py-3 text-xs whitespace-nowrap transition-colors border-b-2",
                isActive
                  ? "text-text-primary border-[var(--nav-active-fg)]"
                  : "text-text-muted border-transparent hover:text-text-secondary"
              )}
            >
              <Icon className="h-3.5 w-3.5 shrink-0" />
              <span>{item.label}</span>
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
