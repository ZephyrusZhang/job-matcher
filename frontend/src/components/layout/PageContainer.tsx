export function PageContainer({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-4 py-4 md:p-[var(--spacing-page)] max-w-7xl mx-auto w-full">
      {children}
    </div>
  )
}
