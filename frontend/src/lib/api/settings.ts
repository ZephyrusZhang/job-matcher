import { apiGet, apiPatch } from './client'
import type { Settings } from '@/types/settings'

export function getSettings() {
  return apiGet<Settings>('/api/settings')
}

export function updateSettings(settings: Partial<Settings>) {
  return apiPatch<Settings>('/api/settings', settings)
}
