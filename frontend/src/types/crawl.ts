export interface CrawlTask {
  id: string
  company_id: string
  company_name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  jobs_found: number
  jobs_new: number
  jobs_updated: number
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}
