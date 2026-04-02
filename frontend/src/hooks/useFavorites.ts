import { useEffect } from 'react'
import { useFavoriteStore } from '@/store/useFavoriteStore'

export function useFavorites() {
  const { favoriteIds, summary, toggle, fetchFavorites, fetchSummary, isFavorited } =
    useFavoriteStore()

  useEffect(() => {
    fetchFavorites()
    fetchSummary()
  }, [fetchFavorites, fetchSummary])

  return { favoriteIds, summary, toggle, isFavorited }
}
