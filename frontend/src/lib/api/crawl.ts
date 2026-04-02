import { apiGet, apiPost } from './client'
import type { CrawlTask } from '@/types/crawl'

export function getCrawlTasks() {
  return apiGet<CrawlTask[]>('/api/crawl/tasks')
}

export function getCrawlTask(taskId: string) {
  return apiGet<CrawlTask>(`/api/crawl/tasks/${taskId}`)
}

export function triggerCrawl(companyId: string) {
  return apiPost<CrawlTask>(`/api/crawl/trigger/${companyId}`)
}
