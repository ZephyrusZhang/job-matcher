import { create } from "zustand"
import {
  createConversation,
  deleteConversation,
  listConversations,
  renameConversation,
} from "@/lib/api/match"
import type { Conversation } from "@/types/match"

interface ConversationStore {
  conversations: Conversation[]
  activeId: string | null
  /** Falls back to the most recent conversation until one is picked. */
  effectiveId: () => string | null
  select: (id: string | null) => void
  fetch: () => Promise<Conversation[]>
  create: () => Promise<string | null>
  rename: (id: string, title: string) => Promise<void>
  remove: (id: string) => Promise<void>
}

/**
 * Conversation list state.
 *
 * Lives in a store rather than on the page because the list is rendered by the
 * app sidebar — keeping /match to a single sidebar instead of two stacked ones.
 */
export const useConversationStore = create<ConversationStore>((set, get) => ({
  conversations: [],
  activeId: null,

  effectiveId: () => get().activeId ?? get().conversations[0]?.id ?? null,

  select: (id) => set({ activeId: id }),

  fetch: async () => {
    try {
      const res = await listConversations()
      const list = res.data ?? []
      set({ conversations: list })
      return list
    } catch {
      set({ conversations: [] })
      return []
    }
  },

  create: async () => {
    const res = await createConversation().catch(() => null)
    if (!res?.data) return null
    set({ activeId: res.data.id })
    await get().fetch()
    return res.data.id
  },

  rename: async (id, title) => {
    await renameConversation(id, title).catch(() => null)
    await get().fetch()
  },

  remove: async (id) => {
    await deleteConversation(id).catch(() => null)
    const list = await get().fetch()
    if (get().activeId === id) {
      set({ activeId: list.length > 0 ? list[0].id : null })
    }
  },
}))
