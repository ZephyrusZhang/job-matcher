import { apiGet, apiPost } from './client'
import type { CrawlTask } from '@/types/crawl'

export function getCrawlTasks() {
  return apiGet<CrawlTask[]>('/api/crawl/tasks')
}

export function getCrawlTask(taskId: string) {
  return apiGet<CrawlTask>(`/api/crawl/tasks/${taskId}`)
}

export function triggerCrawl(companyId: string) {
  return apiPost<CrawlTask>('/api/crawl/trigger', { company_id: companyId })
}

export function cancelCrawlTask(taskId: string) {
  return apiPost<CrawlTask>(`/api/crawl/tasks/${taskId}/cancel`)
}
