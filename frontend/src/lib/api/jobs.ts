import { apiGet } from './client'
import type { Job, JobQueryParams, SearchParams } from '@/types/job'

export function getJobs(params: JobQueryParams) {
  return apiGet<Job[]>('/api/jobs', { ...params })
}

export function getJob(id: string) {
  return apiGet<Job>(`/api/jobs/${id}`)
}

export function searchJobs(params: SearchParams) {
  return apiGet<Job[]>('/api/jobs/search', { ...params })
}
