import { apiGet, apiDelete } from './client'
import { uploadFile } from '@/lib/upload'
import type { ResumeInfo, ResumeUploadResponse } from '@/types/resume'

export function getResume() {
  return apiGet<ResumeInfo>('/api/resume')
}

export function uploadResume(file: File) {
  return uploadFile<ResumeUploadResponse>('/api/resume', file)
}

export function deleteResume() {
  return apiDelete<void>('/api/resume')
}
