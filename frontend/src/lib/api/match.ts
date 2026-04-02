import type { Report, GenerateRequest } from '@/types/report'
import type { SSEEvent } from '@/lib/sse'
import { apiGet } from './client'
import { consumeSSE } from '@/lib/sse'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:3001'

export function getReports() {
  return apiGet<Report[]>('/api/match/reports')
}

export function getReport(reportId: string) {
  return apiGet<Report>(`/api/match/reports/${reportId}`)
}

export function generateReport(request: GenerateRequest): AsyncGenerator<SSEEvent> {
  return consumeSSE(`${API_BASE}/api/match/generate`, request)
}
