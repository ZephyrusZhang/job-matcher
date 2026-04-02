import { create } from 'zustand'
import type { FavoriteSummary } from '@/types/favorite'
import {
  getFavorites,
  getFavoriteSummary,
  addFavorite,
  removeFavorite,
} from '@/lib/api/favorites'

interface FavoriteStore {
  favoriteIds: Set<string>
  summary: FavoriteSummary[]
  toggle: (jobId: string) => Promise<void>
  fetchFavorites: () => Promise<void>
  fetchSummary: () => Promise<void>
  isFavorited: (jobId: string) => boolean
}

export const useFavoriteStore = create<FavoriteStore>((set, get) => ({
  favoriteIds: new Set<string>(),
  summary: [],

  isFavorited: (jobId: string) => get().favoriteIds.has(jobId),

  toggle: async (jobId: string) => {
    const { favoriteIds } = get()
    const wasFavorited = favoriteIds.has(jobId)

    // Optimistic update
    const next = new Set(favoriteIds)
    if (wasFavorited) {
      next.delete(jobId)
    } else {
      next.add(jobId)
    }
    set({ favoriteIds: next })

    try {
      if (wasFavorited) {
        await removeFavorite(jobId)
      } else {
        await addFavorite(jobId)
      }
      // Refresh summary after successful toggle
      await get().fetchSummary()
    } catch {
      // Rollback on failure
      const rollback = new Set(get().favoriteIds)
      if (wasFavorited) {
        rollback.add(jobId)
      } else {
        rollback.delete(jobId)
      }
      set({ favoriteIds: rollback })
    }
  },

  fetchFavorites: async () => {
    try {
      const res = await getFavorites()
      const ids = new Set(res.data.map((item) => item.job_id))
      set({ favoriteIds: ids })
    } catch {
      // ignore
    }
  },

  fetchSummary: async () => {
    try {
      const res = await getFavoriteSummary()
      set({ summary: res.data })
    } catch {
      // ignore
    }
  },
}))
