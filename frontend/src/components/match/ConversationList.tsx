"use client"

import { useEffect, useState } from "react"
import { Check, MoreHorizontal, Pencil, Plus, Trash2, X } from "lucide-react"
import { useConversationStore } from "@/store/useConversationStore"
import { cn } from "@/lib/utils"
import type { Conversation } from "@/types/match"

/**
 * Conversation history, rendered inside the app sidebar.
 *
 * Deliberately not its own panel: /match previously stacked a second sidebar
 * next to the app nav, which read as clutter. The nav has ample unused vertical
 * space, so the list lives there and the page keeps a single sidebar.
 */
export function ConversationList() {
  const conversations = useConversationStore((s) => s.conversations)
  const activeId = useConversationStore((s) => s.activeId)
  const select = useConversationStore((s) => s.select)
  const fetchAll = useConversationStore((s) => s.fetch)
  const create = useConversationStore((s) => s.create)
  const rename = useConversationStore((s) => s.rename)
  const remove = useConversationStore((s) => s.remove)

  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState("")
  const [menuId, setMenuId] = useState<string | null>(null)

  useEffect(() => {
    fetchAll()
  }, [fetchAll])

  const effectiveId = activeId ?? conversations[0]?.id ?? null

  const startRename = (conversation: Conversation) => {
    setEditingId(conversation.id)
    setDraft(conversation.title)
    setMenuId(null)
  }

  const commitRename = (id: string) => {
    const title = draft.trim()
    if (title) rename(id, title)
    setEditingId(null)
  }

  return (
    <div className="mt-1 flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between px-3 pb-1">
        <span className="text-[11px] text-text-muted">对话记录</span>
        <button
          type="button"
          onClick={() => create()}
          className="rounded p-1 text-text-muted transition-colors hover:bg-[var(--nav-hover-bg)] hover:text-text-primary"
          aria-label="新对话"
          title="新对话"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-1.5">
        {conversations.length === 0 ? (
          <p className="px-1.5 py-2 text-xs text-text-muted">还没有对话</p>
        ) : (
          conversations.map((conversation) => {
            const isActive = conversation.id === effectiveId
            const isEditing = editingId === conversation.id

            return (
              <div
                key={conversation.id}
                className={cn(
                  "group relative mb-0.5 rounded-[var(--radius-sm)]",
                  isActive
                    ? "bg-[var(--nav-active-bg)]"
                    : "hover:bg-[var(--nav-hover-bg)]",
                )}
              >
                {isEditing ? (
                  <div className="flex items-center gap-1 px-1.5 py-1">
                    <input
                      autoFocus
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitRename(conversation.id)
                        if (e.key === "Escape") setEditingId(null)
                      }}
                      className="min-w-0 flex-1 rounded border border-border-default bg-bg-primary px-1.5 py-0.5 text-xs text-text-primary outline-none"
                    />
                    <button
                      type="button"
                      onClick={() => commitRename(conversation.id)}
                      className="text-text-muted hover:text-text-primary"
                      aria-label="确认"
                    >
                      <Check className="h-3 w-3" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditingId(null)}
                      className="text-text-muted hover:text-text-primary"
                      aria-label="取消"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={() => select(conversation.id)}
                      className={cn(
                        "block w-full truncate px-2 py-1.5 pr-7 text-left text-xs",
                        isActive
                          ? "text-[var(--nav-active-fg)]"
                          : "text-text-secondary",
                      )}
                      title={conversation.title}
                    >
                      {conversation.title || "新对话"}
                    </button>

                    <button
                      type="button"
                      onClick={() =>
                        setMenuId(menuId === conversation.id ? null : conversation.id)
                      }
                      className={cn(
                        "absolute right-1 top-1/2 -translate-y-1/2 rounded p-0.5 text-text-muted transition-opacity hover:text-text-primary",
                        menuId === conversation.id
                          ? "opacity-100"
                          : "opacity-0 group-hover:opacity-100",
                      )}
                      aria-label="更多操作"
                    >
                      <MoreHorizontal className="h-3 w-3" />
                    </button>

                    {menuId === conversation.id && (
                      <div className="absolute right-1 top-full z-30 mt-0.5 w-24 overflow-hidden rounded-md border border-border-default bg-bg-elevated shadow-lg">
                        <button
                          type="button"
                          onClick={() => startRename(conversation)}
                          className="flex w-full items-center gap-1.5 px-2 py-1.5 text-xs text-text-primary hover:bg-bg-tertiary"
                        >
                          <Pencil className="h-3 w-3" />
                          重命名
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setMenuId(null)
                            remove(conversation.id)
                          }}
                          className="flex w-full items-center gap-1.5 px-2 py-1.5 text-xs text-red-400 hover:bg-bg-tertiary"
                        >
                          <Trash2 className="h-3 w-3" />
                          删除
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
