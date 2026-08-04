"use client"

import { useState } from "react"
import { Check, MoreHorizontal, Pencil, Plus, Trash2, X } from "lucide-react"
import { cn } from "@/lib/utils"
import type { Conversation } from "@/types/match"

interface ConversationSidebarProps {
  conversations: Conversation[]
  activeId: string | null
  onSelect: (id: string) => void
  onCreate: () => void
  onRename: (id: string, title: string) => void
  onDelete: (id: string) => void
}

/**
 * Flat, ungrouped list of every conversation, most recently used first.
 */
export function ConversationSidebar({
  conversations,
  activeId,
  onSelect,
  onCreate,
  onRename,
  onDelete,
}: ConversationSidebarProps) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState("")
  const [menuId, setMenuId] = useState<string | null>(null)

  const startRename = (conversation: Conversation) => {
    setEditingId(conversation.id)
    setDraft(conversation.title)
    setMenuId(null)
  }

  const commitRename = (id: string) => {
    const title = draft.trim()
    if (title) onRename(id, title)
    setEditingId(null)
  }

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-border-subtle bg-bg-secondary">
      <div className="p-2">
        <button
          type="button"
          onClick={onCreate}
          className="flex w-full items-center gap-2 rounded-md border border-border-subtle px-3 py-2 text-sm text-text-primary transition-colors hover:bg-bg-tertiary"
        >
          <Plus className="h-4 w-4" />
          新对话
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {conversations.length === 0 ? (
          <p className="px-3 py-6 text-xs text-text-muted">还没有对话</p>
        ) : (
          conversations.map((conversation) => {
            const isActive = conversation.id === activeId
            const isEditing = editingId === conversation.id

            return (
              <div
                key={conversation.id}
                className={cn(
                  "group relative mb-0.5 rounded-md",
                  isActive ? "bg-bg-tertiary" : "hover:bg-bg-tertiary/60",
                )}
              >
                {isEditing ? (
                  <div className="flex items-center gap-1 px-2 py-1.5">
                    <input
                      autoFocus
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitRename(conversation.id)
                        if (e.key === "Escape") setEditingId(null)
                      }}
                      className="min-w-0 flex-1 rounded border border-border-default bg-bg-primary px-1.5 py-0.5 text-sm text-text-primary outline-none"
                    />
                    <button
                      type="button"
                      onClick={() => commitRename(conversation.id)}
                      className="text-text-muted hover:text-text-primary"
                      aria-label="确认重命名"
                    >
                      <Check className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditingId(null)}
                      className="text-text-muted hover:text-text-primary"
                      aria-label="取消重命名"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={() => onSelect(conversation.id)}
                      className="block w-full truncate px-3 py-2 pr-8 text-left text-sm text-text-primary"
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
                        "absolute right-1 top-1/2 -translate-y-1/2 rounded p-1 text-text-muted transition-opacity hover:text-text-primary",
                        menuId === conversation.id
                          ? "opacity-100"
                          : "opacity-0 group-hover:opacity-100",
                      )}
                      aria-label="更多操作"
                    >
                      <MoreHorizontal className="h-3.5 w-3.5" />
                    </button>

                    {menuId === conversation.id && (
                      <div className="absolute right-1 top-full z-20 mt-0.5 w-28 overflow-hidden rounded-md border border-border-default bg-bg-elevated shadow-lg">
                        <button
                          type="button"
                          onClick={() => startRename(conversation)}
                          className="flex w-full items-center gap-2 px-2.5 py-1.5 text-xs text-text-primary hover:bg-bg-tertiary"
                        >
                          <Pencil className="h-3 w-3" />
                          重命名
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setMenuId(null)
                            onDelete(conversation.id)
                          }}
                          className="flex w-full items-center gap-2 px-2.5 py-1.5 text-xs text-red-400 hover:bg-bg-tertiary"
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
    </aside>
  )
}
