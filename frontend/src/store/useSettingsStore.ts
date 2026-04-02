import { create } from 'zustand'
import type { Settings } from '@/types/settings'
import { getSettings, updateSettings } from '@/lib/api/settings'

interface SettingsStore {
  density: 'comfortable' | 'compact'
  language: 'zh' | 'en'
  update: (patch: Partial<Settings>) => Promise<void>
  fetchSettings: () => Promise<void>
}

export const useSettingsStore = create<SettingsStore>((set) => ({
  density: 'comfortable',
  language: 'zh',

  update: async (patch: Partial<Settings>) => {
    try {
      const res = await updateSettings(patch)
      set({
        density: res.data.display_density,
        language: res.data.language,
      })
    } catch {
      throw new Error('Settings update failed')
    }
  },

  fetchSettings: async () => {
    try {
      const res = await getSettings()
      set({
        density: res.data.display_density,
        language: res.data.language,
      })
    } catch {
      // ignore, keep defaults
    }
  },
}))
