export interface ResumeInfo {
  filename: string
  parsed: {
    skills: string[]
    experience_years: number | null
    education: string | null
    raw_text: string
  }
  uploaded_at: string
}

export interface ResumeUploadResponse extends ResumeInfo {
  cleared: {
    reports_deleted: number
    messages_deleted: number
  }
}
