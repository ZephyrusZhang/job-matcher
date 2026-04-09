"use client"

import { useEffect } from "react"
import { create } from "zustand"
import { AlertCircle, CheckCircle2, Info, X } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Minimal in-app toast system.
 *
 * Replaces native `alert()` / `confirm()` dialogs so API errors (e.g. HTTP 403
 * from read-only mode, validation failures, network errors) surface with the
 * app's own dark theme instead of the browser chrome.
 *
 * Usage:
 *     import { toast } from "@/components/ui/toast"
 *     toast.error("添加失败")
 *     toast.success("保存成功")
 *     toast.info("提示信息")
 *
 * Mount `<Toaster />` once in the root layout.
 */

export type ToastVariant = "error" | "success" | "info"

interface ToastItem {
  id: number
  variant: ToastVariant
  title: string
  description?: string
}

interface ToastStore {
  items: ToastItem[]
  push: (item: Omit<ToastItem, "id">) => number
  dismiss: (id: number) => void
}

const useToastStore = create<ToastStore>((set) => ({
  items: [],
  push: (item) => {
    const id = Date.now() + Math.random()
    set((state) => ({ items: [...state.items, { id, ...item }] }))
    return id
  },
  dismiss: (id) =>
    set((state) => ({ items: state.items.filter((t) => t.id !== id) })),
}))

const DEFAULT_TIMEOUT: Record<ToastVariant, number> = {
  error: 5000,
  success: 3000,
  info: 4000,
}

function show(variant: ToastVariant, title: string, description?: string) {
  const id = useToastStore.getState().push({ variant, title, description })
  if (typeof window !== "undefined") {
    window.setTimeout(
      () => useToastStore.getState().dismiss(id),
      DEFAULT_TIMEOUT[variant],
    )
  }
  return id
}

export const toast = {
  error: (title: string, description?: string) => show("error", title, description),
  success: (title: string, description?: string) => show("success", title, description),
  info: (title: string, description?: string) => show("info", title, description),
  dismiss: (id: number) => useToastStore.getState().dismiss(id),
}

const VARIANT_STYLES: Record<
  ToastVariant,
  { icon: React.ComponentType<{ className?: string }>; iconClass: string; border: string }
> = {
  error: {
    icon: AlertCircle,
    iconClass: "text-red-400",
    border: "border-red-500/30",
  },
  success: {
    icon: CheckCircle2,
    iconClass: "text-emerald-400",
    border: "border-emerald-500/30",
  },
  info: {
    icon: Info,
    iconClass: "text-blue-400",
    border: "border-blue-500/30",
  },
}

export function Toaster() {
  const items = useToastStore((s) => s.items)
  const dismiss = useToastStore((s) => s.dismiss)

  // Enable closing the top-most toast via ESC for keyboard users.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && items.length > 0) {
        dismiss(items[items.length - 1].id)
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [items, dismiss])

  if (items.length === 0) return null

  return (
    <div
      aria-live="polite"
      aria-atomic="true"
      className="fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none max-w-[min(92vw,380px)]"
    >
      {items.map((t) => {
        const { icon: Icon, iconClass, border } = VARIANT_STYLES[t.variant]
        return (
          <div
            key={t.id}
            role="status"
            className={cn(
              "pointer-events-auto flex items-start gap-3 rounded-[var(--radius-sm)] border bg-bg-elevated px-4 py-3 shadow-lg animate-in fade-in slide-in-from-top-2",
              border,
            )}
          >
            <Icon className={cn("h-4 w-4 mt-0.5 shrink-0", iconClass)} />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-text-primary font-medium break-words">
                {t.title}
              </p>
              {t.description && (
                <p className="text-xs text-text-secondary mt-1 break-words leading-relaxed">
                  {t.description}
                </p>
              )}
            </div>
            <button
              onClick={() => dismiss(t.id)}
              className="shrink-0 text-text-muted hover:text-text-primary transition-colors cursor-pointer"
              aria-label="关闭"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )
      })}
    </div>
  )
}
