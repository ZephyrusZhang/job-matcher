import { apiGet, apiPost, apiDelete } from './client'
import type { Company, CompanyCreate, CompanyUpdate } from '@/types/company'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:3001'

export function getCompanies() {
  return apiGet<Company[]>('/api/companies')
}

export function getCompany(id: string) {
  return apiGet<Company>(`/api/companies/${id}`)
}

export function createCompany(data: CompanyCreate) {
  return apiPost<Company>('/api/companies', data)
}

export async function updateCompany(id: string, data: CompanyUpdate) {
  const res = await fetch(`${API_BASE}/api/companies/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  const body = await res.json()
  if (!res.ok) {
    throw new Error(body.error?.message ?? 'Update failed')
  }
  return body
}

export function deleteCompany(id: string) {
  return apiDelete<null>(`/api/companies/${id}`)
}

// Crawler script endpoints

export interface CrawlerScript {
  company_id: string
  code: string
  updated_at: string
}

export function getCrawlerScript(companyId: string) {
  return apiGet<CrawlerScript | null>(`/api/companies/${companyId}/crawler-script`)
}

export async function saveCrawlerScript(companyId: string, code: string) {
  const res = await fetch(`${API_BASE}/api/companies/${companyId}/crawler-script`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  })
  const body = await res.json()
  if (!res.ok) throw new Error(body.error?.message ?? 'Save failed')
  return body
}

export function deleteCrawlerScript(companyId: string) {
  return apiDelete<null>(`/api/companies/${companyId}/crawler-script`)
}
