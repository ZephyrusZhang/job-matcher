"use client"

import { useState } from "react"
import { Bot, FileCode2, Loader2, Play } from "lucide-react"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import type { CrawlMode } from "@/types/crawl"

interface CrawlTriggerButtonProps {
  hasScript: boolean
  isTriggering: boolean
  onTrigger: (mode: CrawlMode) => void
}

/**
 * Starts a crawl, asking which of the two ways to run it.
 *
 * The choice used to be implicit and the wrong way round: a stored script was
 * always preferred, so pressing the button on a site whose markup had changed
 * silently re-ran the stale script instead of rewriting it.
 */
export function CrawlTriggerButton({
  hasScript,
  isTriggering,
  onTrigger,
}: CrawlTriggerButtonProps) {
  const [open, setOpen] = useState(false)

  const pick = (mode: CrawlMode) => {
    setOpen(false)
    onTrigger(mode)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        disabled={isTriggering}
        title="爬取"
        aria-label="爬取"
        className="inline-flex size-6 items-center justify-center rounded text-blue-400 transition-colors hover:bg-blue-500/10 hover:text-blue-300 disabled:opacity-30"
      >
        {isTriggering ? (
          <Loader2 className="size-3.5 animate-spin" />
        ) : (
          <Play className="size-3.5" />
        )}
      </PopoverTrigger>
      <PopoverContent align="end" className="w-64 p-1.5">
        <button
          type="button"
          onClick={() => pick("agent")}
          className="flex w-full items-start gap-2.5 rounded px-2 py-2 text-left transition-colors hover:bg-bg-tertiary"
        >
          <Bot className="mt-0.5 size-3.5 shrink-0 text-blue-400" />
          <span className="min-w-0">
            <span className="block text-sm text-text-primary">重新生成脚本</span>
            <span className="block text-xs text-text-muted">
              让 Agent 重新分析站点并写一份新的爬虫，较慢
            </span>
          </span>
        </button>

        <button
          type="button"
          onClick={() => pick("cached")}
          disabled={!hasScript}
          className="flex w-full items-start gap-2.5 rounded px-2 py-2 text-left transition-colors hover:bg-bg-tertiary disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"
        >
          <FileCode2 className="mt-0.5 size-3.5 shrink-0 text-emerald-400" />
          <span className="min-w-0">
            <span className="block text-sm text-text-primary">运行已有脚本</span>
            <span className="block text-xs text-text-muted">
              {hasScript
                ? "直接执行已保存的爬虫，不调用模型"
                : "尚未保存脚本，先生成一次"}
            </span>
          </span>
        </button>
      </PopoverContent>
    </Popover>
  )
}
