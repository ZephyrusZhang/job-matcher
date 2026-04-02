import { useEffect } from 'react'
import { useResumeStore } from '@/store/useResumeStore'

export function useResume() {
  const { resume, isUploading, upload, fetchResume, deleteResume } = useResumeStore()

  useEffect(() => {
    fetchResume()
  }, [fetchResume])

  return { resume, isUploading, upload, deleteResume }
}
