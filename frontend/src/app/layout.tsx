import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import { AppShell } from "@/components/layout/AppShell"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Toaster } from "@/components/ui/toast"
import { ConfirmHost } from "@/components/ui/confirm"
import { THEME_INIT_SCRIPT } from "@/lib/theme"

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
})

export const metadata: Metadata = {
  title: "JobMatcher — 智能岗位聚合与匹配平台",
  description: "自动聚合技术岗位，智能匹配推荐",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  // NOTE: The `dark` / `light` class on <html> is managed entirely by the
  // inline boot script below and by ThemeToggle. We deliberately do NOT
  // put it in `className` here, because React would otherwise treat it as
  // the source of truth and revert any class added by our toggle on
  // subsequent re-renders. `suppressHydrationWarning` keeps React from
  // complaining about the SSR/CSR className mismatch.
  return (
    <html lang="zh" className={`${inter.variable} h-full antialiased`} suppressHydrationWarning>
      <head>
        {/* Runs before React hydrates to avoid a flash of the wrong theme.
            This is the *only* code that adds `dark` / `light` to <html>
            during initial paint. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="min-h-full flex flex-col font-sans">
        <TooltipProvider>
          <AppShell>{children}</AppShell>
          <Toaster />
          <ConfirmHost />
        </TooltipProvider>
      </body>
    </html>
  )
}
