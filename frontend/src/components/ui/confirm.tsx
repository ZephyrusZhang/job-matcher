"use client"

import { create } from "zustand"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"

/**
 * Imperative confirm dialog with the app's own dark theme.
 *
 * Replaces native `window.confirm()` so destructive actions get styled
 * prompts instead of the browser chrome.
 *
 * Usage:
 *     import { confirmDialog } from "@/components/ui/confirm"
 *     if (!(await confirmDialog({
 *       title: "删除公司",
 *       description: "确定要删除「字节跳动」吗？",
 *       confirmLabel: "删除",
 *       destructive: true,
 *     }))) return
 *
 * Mount `<ConfirmHost />` once in the root layout.
 */

interface ConfirmRequest {
  title: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  /** Styles the confirm button as destructive (red). */
  destructive?: boolean
}

interface ConfirmStore {
  current: (ConfirmRequest & { resolve: (ok: boolean) => void }) | null
  open: (req: ConfirmRequest) => Promise<boolean>
  close: (result: boolean) => void
}

const useConfirmStore = create<ConfirmStore>((set, get) => ({
  current: null,
  open: (req) =>
    new Promise<boolean>((resolve) => {
      // If a previous dialog was still pending, reject it as cancelled.
      const prev = get().current
      if (prev) prev.resolve(false)
      set({ current: { ...req, resolve } })
    }),
  close: (result) => {
    const cur = get().current
    if (cur) {
      cur.resolve(result)
      set({ current: null })
    }
  },
}))

export function confirmDialog(req: ConfirmRequest): Promise<boolean> {
  return useConfirmStore.getState().open(req)
}

export function ConfirmHost() {
  const current = useConfirmStore((s) => s.current)
  const close = useConfirmStore((s) => s.close)

  const open = current !== null

  return (
    <AlertDialog
      open={open}
      onOpenChange={(next) => {
        if (!next) close(false)
      }}
    >
      {current && (
        <AlertDialogContent size="sm">
          <AlertDialogHeader>
            <AlertDialogTitle>{current.title}</AlertDialogTitle>
            {current.description && (
              <AlertDialogDescription>
                {current.description}
              </AlertDialogDescription>
            )}
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>
              {current.cancelLabel ?? "取消"}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => close(true)}
              className={
                current.destructive
                  ? "bg-red-500 hover:bg-red-500/90 text-[white] border-transparent"
                  : undefined
              }
            >
              {current.confirmLabel ?? "确定"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      )}
    </AlertDialog>
  )
}
