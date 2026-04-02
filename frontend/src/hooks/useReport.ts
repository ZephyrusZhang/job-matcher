import { useState, useCallback } from 'react'
import type { Report, GenerateRequest } from '@/types/report'
import { getReport } from '@/lib/api/match'
import { useSSE } from './useSSE'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:3001'

export function useReport() {
  const [report, setReport] = useState<Report | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const sse = useSSE()

  const loadReport = useCallback(async (reportId: string) => {
    try {
      const res = await getReport(reportId)
      setReport(res.data)
    } catch {
      setReport(null)
    }
  }, [])

  const generateMatchReport = useCallback(
    async (request: GenerateRequest) => {
      setIsGenerating(true)
      sse.reset()
      try {
        await sse.start(`${API_BASE}/api/match/generate`, request)
        // After stream completes, load the full report if we got a reportId
        if (sse.reportId) {
          await loadReport(sse.reportId)
        }
      } finally {
        setIsGenerating(false)
      }
    },
    [sse, loadReport],
  )

  const generateCompareReport = useCallback(
    async (jobIds: string[]) => {
      setIsGenerating(true)
      sse.reset()
      try {
        await sse.start(`${API_BASE}/api/compare`, { job_ids: jobIds })
      } finally {
        setIsGenerating(false)
      }
    },
    [sse],
  )

  return {
    report,
    isGenerating,
    content: sse.content,
    isStreaming: sse.isStreaming,
    reportId: sse.reportId,
    loadReport,
    generateMatchReport,
    generateCompareReport,
    stopGeneration: sse.stop,
    resetReport: sse.reset,
  }
}
