import type { SSEEvent } from '@/lib/sse'
import { consumeSSE } from '@/lib/sse'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:3001'

export function compareJobs(jobIds: string[]): AsyncGenerator<SSEEvent> {
  return consumeSSE(`${API_BASE}/api/compare`, { job_ids: jobIds })
}
