export function PageContainer({ children }: { children: React.ReactNode }) {
  return (
    <div className="p-[var(--spacing-page)] max-w-7xl mx-auto w-full">
      {children}
    </div>
  )
}
