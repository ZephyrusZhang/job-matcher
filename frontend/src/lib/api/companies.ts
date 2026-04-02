import { apiGet } from './client'
import type { Company } from '@/types/company'

export function getCompanies() {
  return apiGet<Company[]>('/api/companies')
}

export function getCompany(id: string) {
  return apiGet<Company>(`/api/companies/${id}`)
}
