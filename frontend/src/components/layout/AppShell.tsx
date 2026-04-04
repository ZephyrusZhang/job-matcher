"use client"

import { Sidebar } from "./Sidebar"
import { MobileNav } from "./MobileNav"
import { FloatingFavorites } from "@/components/common/FloatingFavorites"

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <MobileNav />
        <main className="flex-1 overflow-y-auto bg-bg-primary">
          {children}
        </main>
      </div>
      <FloatingFavorites />
    </div>
  )
}
