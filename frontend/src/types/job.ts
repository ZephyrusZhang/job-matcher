export interface Job {
  id: string
  title: string
  category: string
  company: { id: string; name: string }
  location: string[]
  job_type: string | null
  responsibilities: string
  requirements: { must_have: string[]; nice_to_have: string[] }
  department: string | null
  department_product: string | null
  education: string | null
  experience: string | null
  posted_date: string | null
  source_url: string
  summary: string | null
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
