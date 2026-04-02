import { useState, useCallback, useRef } from 'react'
import type { Job, JobQueryParams } from '@/types/job'
import { getJobs } from '@/lib/api/jobs'

export function useJobs() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [page, setPage] = useState(1)
  const paramsRef = useRef<JobQueryParams | null>(null)

  const loadJobs = useCallback(async (params: JobQueryParams) => {
    paramsRef.current = params
    setIsLoading(true)
    setPage(1)
    try {
      const res = await getJobs({ ...params, page: '1' })
      setJobs(res.data)
      const pagination = res.pagination
      setHasMore(pagination ? pagination.page < pagination.total_pages : false)
    } catch {
      setJobs([])
      setHasMore(false)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const loadMore = useCallback(async () => {
    if (!paramsRef.current || isLoading || !hasMore) return

    const nextPage = page + 1
    setIsLoading(true)
    try {
      const res = await getJobs({
        ...paramsRef.current,
        page: String(nextPage),
      })
      setJobs((prev) => [...prev, ...res.data])
      setPage(nextPage)
      const pagination = res.pagination
      setHasMore(pagination ? pagination.page < pagination.total_pages : false)
    } catch {
      setHasMore(false)
    } finally {
      setIsLoading(false)
    }
  }, [page, isLoading, hasMore])

  const reset = useCallback(() => {
    setJobs([])
    setIsLoading(false)
    setHasMore(true)
    setPage(1)
    paramsRef.current = null
  }, [])

  return { jobs, isLoading, hasMore, page, loadJobs, loadMore, reset }
}
