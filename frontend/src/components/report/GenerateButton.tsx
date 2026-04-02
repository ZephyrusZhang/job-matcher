"use client"

import { Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"

interface GenerateButtonProps {
  label: string
  isGenerating: boolean
  disabled: boolean
  onClick: () => void
}

export function GenerateButton({ label, isGenerating, disabled, onClick }: GenerateButtonProps) {
  return (
    <Button
      onClick={onClick}
      disabled={disabled || isGenerating}
      className="bg-accent-main text-bg-primary font-medium rounded-[var(--radius-sm)] px-6 py-2 hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {isGenerating ? (
        <>
          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          生成中...
        </>
      ) : (
        label
      )}
    </Button>
  )
}
