export interface Report {
  report_id: string
  company_id: string
  content: string
  job_ids: string[]
  preferences: {
    interest: string
    additional?: string
  }
  created_at: string
}

export interface GenerateRequest {
  company_id: string
  preferences: {
    interest: string
    additional?: string
  }
}
