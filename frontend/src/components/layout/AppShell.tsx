"use client"

import { Sidebar } from "./Sidebar"
import { FloatingFavorites } from "@/components/common/FloatingFavorites"

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-bg-primary">
        {children}
      </main>
      <FloatingFavorites />
    </div>
  )
}
