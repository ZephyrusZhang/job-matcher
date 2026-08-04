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
  fetch: () => Promise<Conversation[]>
  create: () => Promise<string | null>
  rename: (id: string, title: string) => Promise<void>
  remove: (id: string) => Promise<void>
}

/**
 * Conversation list state.
 *
 * Only the list lives here — which conversation is open is expressed by the
 * URL (`/match/chat/[id]`), so there is no selection to keep in sync.
 */
export const useConversationStore = create<ConversationStore>((set, get) => ({
  conversations: [],

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
    await get().fetch()
    return res.data.id
  },

  rename: async (id, title) => {
    await renameConversation(id, title).catch(() => null)
    await get().fetch()
  },

  remove: async (id) => {
    await deleteConversation(id).catch(() => null)
    await get().fetch()
  },
}))
