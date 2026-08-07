"use client"

import { useState } from "react"
import { Check, ChevronDown, ChevronRight, Loader2, Wrench, X } from "lucide-react"
import { cn } from "@/lib/utils"
import type { TraceStep } from "@/types/match"

/** Render tool arguments compactly enough to sit on the collapsed row. */
function summarizeArgs(args: TraceStep["args"]): string {
  if (!args) return ""
  if (typeof args === "string") return args.slice(0, 50)

  const parts: string[] = []
  for (const [key, value] of Object.entries(args)) {
    if (key === "top_k" || value === null || value === undefined || value === "") continue
    if (Array.isArray(value)) {
      if (value.length) parts.push(value.join("·"))
    } else {
      parts.push(String(value))
    }
  }
  return parts.join(" / ").slice(0, 50)
}

function StatusDot({ step }: { step: TraceStep }) {
  return (
    <span className="absolute -left-[21px] top-1 flex h-4 w-4 items-center justify-center rounded-full bg-bg-primary">
      {step.pending ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin text-text-secondary" />
      ) : step.ok === false ? (
        <X className="h-3.5 w-3.5 text-red-500" />
      ) : (
        <Check className="h-3.5 w-3.5 text-emerald-500" />
      )}
    </span>
  )
}

function ToolStep({ step }: { step: TraceStep }) {
  const [open, setOpen] = useState(false)
  const args = summarizeArgs(step.args)

  return (
    <div className="relative">
      <StatusDot step={step} />
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex w-full items-center gap-2 rounded-md border px-2.5 py-1.5 text-left transition-colors",
          "border-border-subtle bg-bg-secondary hover:border-border-default",
        )}
      >
        <Wrench className="h-3.5 w-3.5 shrink-0 text-text-muted" />
        <span className="shrink-0 text-xs font-medium text-text-secondary">
          {step.label || step.name}
        </span>
        {args && <span className="truncate text-xs text-text-muted">{args}</span>}
        <span className="ml-auto flex shrink-0 items-center gap-1.5 text-xs text-text-muted">
          {step.summary}
          <ChevronDown className={cn("h-3 w-3 transition-transform", open && "rotate-180")} />
        </span>
      </button>

      {open && (
        <div className="mt-1 space-y-1.5 rounded-md border border-border-subtle bg-bg-tertiary/50 p-2">
          <div>
            <div className="mb-0.5 text-[11px] text-text-muted">参数</div>
            <pre className="overflow-x-auto text-[11px] leading-relaxed text-text-secondary">
              {JSON.stringify(step.args ?? {}, null, 2)}
            </pre>
          </div>
          {step.observation && (
            <div>
              {/* The observation is exactly what the model read back, which is
                  what makes the next narration step explicable. */}
              <div className="mb-0.5 text-[11px] text-text-muted">返回结果</div>
              <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-all text-[11px] leading-relaxed text-text-secondary">
                {step.observation}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

interface ThinkingTraceProps {
  steps: TraceStep[]
  isStreaming?: boolean
}

/**
 * The agent's reasoning before its final answer.
 *
 * Replays narration and tool calls in the order they happened — the model
 * narrates, calls a tool, reads the observation, then narrates again — so the
 * trace explains *why* each step followed the last.
 */
export function ThinkingTrace({ steps, isStreaming = false }: ThinkingTraceProps) {
  const [collapsed, setCollapsed] = useState(false)
  if (steps.length === 0) return null

  const toolCount = steps.filter((s) => s.type === "tool").length

  return (
    <div className="mb-3">
      <button
        type="button"
        onClick={() => setCollapsed((v) => !v)}
        className="flex items-center gap-1 text-xs text-text-muted transition-colors hover:text-text-secondary"
      >
        {collapsed ? (
          <ChevronRight className="h-3.5 w-3.5" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5" />
        )}
        思考过程
        {collapsed && toolCount > 0 && (
          <span className="text-text-muted">· {toolCount} 步</span>
        )}
        {isStreaming && <Loader2 className="ml-1 h-3 w-3 animate-spin text-text-secondary" />}
      </button>

      {!collapsed && (
        <div className="ml-[7px] mt-2 space-y-2 border-l border-border-subtle pl-5">
          {steps.map((step) =>
            step.type === "tool" ? (
              <ToolStep key={`tool-${step.index}`} step={step} />
            ) : (
              <p
                key={`say-${step.index}`}
                className="whitespace-pre-wrap text-xs leading-relaxed text-text-secondary"
              >
                {step.content}
              </p>
            ),
          )}
        </div>
      )}
    </div>
  )
}
