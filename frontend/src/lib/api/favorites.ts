import { apiGet, apiPost, apiDelete } from './client'
import type { FavoriteItem, FavoriteSummary } from '@/types/favorite'

export function getFavorites() {
  return apiGet<FavoriteItem[]>('/api/favorites')
}

export function getFavoriteSummary() {
  return apiGet<FavoriteSummary[]>('/api/favorites/summary')
}

export function addFavorite(jobId: string) {
  return apiPost<{ job_id: string }>(`/api/favorites/${jobId}`)
}

export function removeFavorite(jobId: string) {
  return apiDelete<void>(`/api/favorites/${jobId}`)
}
