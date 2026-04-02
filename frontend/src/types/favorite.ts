export interface FavoriteItem {
  job_id: string
  title: string
  category: string
  company_name: string
  location: string | null
  favorited_at: string
}

export interface FavoriteSummary {
  company_id: string
  company_name: string
  count: number
}
