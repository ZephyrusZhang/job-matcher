import { create } from 'zustand'
import type { Company } from '@/types/company'
import { getCompanies } from '@/lib/api/companies'

interface CompanyStore {
  companies: Company[]
  selectedId: string | null
  isLoading: boolean
  setSelected: (id: string) => void
  fetchCompanies: () => Promise<void>
}

export const useCompanyStore = create<CompanyStore>((set) => ({
  companies: [],
  selectedId: null,
  isLoading: false,
  setSelected: (id) => set({ selectedId: id }),
  fetchCompanies: async () => {
    set({ isLoading: true })
    try {
      const res = await getCompanies()
      set({ companies: res.data, isLoading: false })
    } catch {
      set({ isLoading: false })
    }
  },
}))
