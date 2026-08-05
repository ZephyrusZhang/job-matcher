"use client"

import { useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Check, MoreHorizontal, Pencil, Plus, Trash2, X } from "lucide-react"
import { useConversationStore } from "@/store/useConversationStore"
import { SESSION_PARAM, conversationHref } from "@/lib/matchRoutes"
import { cn } from "@/lib/utils"
import type { Conversation } from "@/types/match"

/** How often the sidebar re-checks which conversations have a live turn. */
const LIVE_POLL_MS = 5000

/**
 * Marks a conversation whose turn is still being generated.
 *
 * Sits in the row's trailing slot, where the overflow menu appears on hover —
 * the menu takes precedence, since it is only shown deliberately.
 */
function RunningDot({ active }: { active: boolean }) {
  return (
    <span
      className="absolute right-2 top-1/2 flex size-1.5 -translate-y-1/2 group-hover:opacity-0"
      title="正在生成"
      aria-label="正在生成"
    >
      <span
        className={cn(
          "absolute inline-flex size-full animate-ping rounded-full opacity-75",
          active ? "bg-[var(--nav-active-fg)]" : "bg-blue-400",
        )}
      />
      <span
        className={cn(
          "relative inline-flex size-full rounded-full",
          active ? "bg-[var(--nav-active-fg)]" : "bg-blue-400",
        )}
      />
    </span>
  )
}

/**
 * Conversation history, rendered inside the app sidebar on every page.
 *
 * Deliberately not its own panel — a second sidebar next to the app nav read as
 * clutter. Because it is always visible, picking or creating a conversation
 * also routes to /match, which is the only page that can display one.
 */
export function ConversationList() {
  const conversations = useConversationStore((s) => s.conversations)
  const fetchAll = useConversationStore((s) => s.fetch)
  const create = useConversationStore((s) => s.create)
  const rename = useConversationStore((s) => s.rename)
  const remove = useConversationStore((s) => s.remove)

  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState("")
  const [menuId, setMenuId] = useState<string | null>(null)
  const router = useRouter()
  const searchParams = useSearchParams()
  // No conversation is selected by default; only the URL marks one active.
  const activeId = searchParams.get(SESSION_PARAM)

  useEffect(() => {
    fetchAll()
    // A turn outlives the request that started it, so it can be running in
    // another tab or have been left behind by a reload. Polling is the only
    // way this list learns about that; the interval is slow because the
    // conversation you are driving updates itself through the store.
    const timer = setInterval(fetchAll, LIVE_POLL_MS)
    return () => clearInterval(timer)
  }, [fetchAll])

  const startRename = (conversation: Conversation) => {
    setEditingId(conversation.id)
    setDraft(conversation.title)
    setMenuId(null)
  }

  const open = (id: string) => router.push(conversationHref(id))

  // A blank chat is just a route — the conversation is created on first send,
  // so the sidebar gains no empty entry.
  const startNew = () => router.push(conversationHref(null))

  const commitRename = (id: string) => {
    const title = draft.trim()
    if (title) rename(id, title)
    setEditingId(null)
  }

  return (
    <div className="mt-1 flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between px-3 pb-1">
        <span className="text-xs text-text-muted">对话记录</span>
        <button
          type="button"
          onClick={startNew}
          className="rounded p-1 text-text-muted transition-colors hover:bg-[var(--nav-hover-bg)] hover:text-text-primary"
          aria-label="新对话"
          title="新对话"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-1.5">
        {conversations.length === 0 ? (
          <p className="px-1.5 py-2 text-sm text-text-muted">还没有对话</p>
        ) : (
          conversations.map((conversation) => {
            const isActive = conversation.id === activeId
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
                      className="min-w-0 flex-1 rounded border border-border-default bg-bg-primary px-1.5 py-1 text-sm text-text-primary outline-none"
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
                      onClick={() => open(conversation.id)}
                      className={cn(
                        "block w-full truncate px-2 py-2 pr-7 text-left text-sm",
                        isActive
                          ? "text-[var(--nav-active-fg)]"
                          : "text-text-secondary",
                      )}
                      title={conversation.title}
                    >
                      {conversation.title || "新对话"}
                    </button>

                    {conversation.is_running && <RunningDot active={isActive} />}

                    <button
                      type="button"
                      onClick={() =>
                        setMenuId(menuId === conversation.id ? null : conversation.id)
                      }
                      className={cn(
                        "absolute right-1 top-1/2 -translate-y-1/2 rounded p-0.5 transition-opacity",
                        // The active row is an inverted surface, so the icon has
                        // to follow that scale — `text-text-primary` is the same
                        // white as `--nav-active-bg` and would vanish into it.
                        isActive
                          ? "text-[var(--nav-active-fg)]/55 hover:bg-black/10 hover:text-[var(--nav-active-fg)]"
                          : "text-text-muted hover:bg-[var(--nav-hover-bg)] hover:text-text-primary",
                        menuId === conversation.id
                          ? "opacity-100"
                          : "opacity-0 group-hover:opacity-100",
                      )}
                      aria-label="更多操作"
                    >
                      <MoreHorizontal className="h-3.5 w-3.5" />
                    </button>

                    {menuId === conversation.id && (
                      <div className="absolute right-1 top-full z-30 mt-0.5 w-28 overflow-hidden rounded-md border border-border-default bg-bg-elevated shadow-lg">
                        <button
                          type="button"
                          onClick={() => startRename(conversation)}
                          className="flex w-full items-center gap-1.5 px-2.5 py-2 text-sm text-text-primary hover:bg-bg-tertiary"
                        >
                          <Pencil className="h-3 w-3" />
                          重命名
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setMenuId(null)
                            remove(conversation.id)
                            if (conversation.id === activeId)
                              router.push(conversationHref(null))
                          }}
                          className="flex w-full items-center gap-1.5 px-2.5 py-2 text-sm text-red-400 hover:bg-bg-tertiary"
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
