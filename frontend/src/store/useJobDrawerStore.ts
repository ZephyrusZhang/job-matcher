import { create } from "zustand"

/**
 * Which job the detail drawer is showing.
 *
 * Job citations are rendered from inside the Markdown tree, several layers
 * below the page component, and `react-markdown` gives no way to thread a
 * callback down to them — so the open/close intent lives in a store instead.
 */
interface JobDrawerStore {
  jobId: string | null
  isOpen: boolean
  open: (jobId: string) => void
  close: () => void
}

export const useJobDrawerStore = create<JobDrawerStore>((set) => ({
  jobId: null,
  isOpen: false,

  open: (jobId: string) => set({ jobId, isOpen: true }),
  // `jobId` is deliberately kept so the panel does not blank out mid-animation.
  close: () => set({ isOpen: false }),
}))
