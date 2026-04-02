"use client"

import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { cn } from "@/lib/utils"

interface ReportRendererProps {
  content: string
  isStreaming: boolean
}

export function ReportRenderer({ content, isStreaming }: ReportRendererProps) {
  if (!content) return null

  return (
    <div className={cn("prose-invert max-w-none", isStreaming && "streaming-cursor")}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="text-lg font-medium text-text-primary mt-6 mb-3">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-base font-medium text-text-primary mt-5 mb-2">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-sm font-medium text-accent-main border-l-2 border-accent-main pl-3 mt-4 mb-2">
              {children}
            </h3>
          ),
          p: ({ children }) => (
            <p className="text-sm text-text-primary leading-relaxed mb-3">{children}</p>
          ),
          ul: ({ children }) => (
            <ul className="text-sm text-text-primary list-disc pl-5 mb-3 space-y-1">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="text-sm text-text-primary list-decimal pl-5 mb-3 space-y-1">{children}</ol>
          ),
          li: ({ children }) => (
            <li className="text-sm text-text-primary leading-relaxed">{children}</li>
          ),
          strong: ({ children }) => (
            <strong className="text-text-primary font-medium">{children}</strong>
          ),
          em: ({ children }) => (
            <em className="text-text-secondary">{children}</em>
          ),
          hr: () => <hr className="border-border-subtle my-4" />,
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-accent-main pl-3 text-sm text-text-secondary italic my-3">
              {children}
            </blockquote>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
