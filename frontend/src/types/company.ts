export interface Company {
  id: string
  name: string
  career_url: string
  crawl_interval_hours: number
  last_crawled_at: string | null
  job_count: number
}
