export interface Job {
  id: string
  title: string
  category: string
  company: { id: string; name: string }
  location: string[]
  job_type: string | null
  /** 职位描述 and 职位要求, both the careers site's own text. */
  description: string | null
  requirements: string | null
  posted_date: string | null
  source_url: string
  is_favorited: boolean
  created_at: string
}

export interface JobQueryParams {
  company_id: string
  category?: string
  location?: string
  job_type?: string
  posted_within?: string
  sort_by?: string
  sort_order?: string
  page?: string
  page_size?: string
}

export interface SearchParams {
  q: string
  company_id?: string
  page?: string
  page_size?: string
}
