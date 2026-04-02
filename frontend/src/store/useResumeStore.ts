import { create } from 'zustand'
import type { ResumeInfo } from '@/types/resume'
import {
  getResume,
  uploadResume as uploadResumeApi,
  deleteResume as deleteResumeApi,
} from '@/lib/api/resume'

interface ResumeStore {
  resume: ResumeInfo | null
  isUploading: boolean
  upload: (file: File) => Promise<void>
  fetchResume: () => Promise<void>
  deleteResume: () => Promise<void>
}

export const useResumeStore = create<ResumeStore>((set) => ({
  resume: null,
  isUploading: false,

  upload: async (file: File) => {
    set({ isUploading: true })
    try {
      const res = await uploadResumeApi(file)
      set({ resume: res.data, isUploading: false })
    } catch {
      set({ isUploading: false })
      throw new Error('Resume upload failed')
    }
  },

  fetchResume: async () => {
    try {
      const res = await getResume()
      set({ resume: res.data })
    } catch {
      set({ resume: null })
    }
  },

  deleteResume: async () => {
    try {
      await deleteResumeApi()
      set({ resume: null })
    } catch {
      throw new Error('Resume delete failed')
    }
  },
}))
