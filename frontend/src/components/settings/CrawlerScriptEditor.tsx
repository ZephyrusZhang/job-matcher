"use client"

import { useEffect, useState, useCallback } from "react"
import { Code2, Save, Trash2, X, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  getCrawlerScript,
  saveCrawlerScript,
  deleteCrawlerScript,
} from "@/lib/api/companies"

import dynamic from "next/dynamic"

const Editor = dynamic(() => import("@monaco-editor/react").then((m) => m.default), {
  ssr: false,
  loading: () => (
    <div className="flex-1 bg-neutral-900 flex items-center justify-center">
      <Loader2 className="size-5 animate-spin text-neutral-500" />
    </div>
  ),
})

interface CrawlerScriptEditorProps {
  companyId: string
  companyName: string
  open: boolean
  onClose: () => void
}

export function CrawlerScriptEditor({
  companyId,
  companyName,
  open,
  onClose,
}: CrawlerScriptEditorProps) {
  const [code, setCode] = useState("")
  const [originalCode, setOriginalCode] = useState("")
  const [updatedAt, setUpdatedAt] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

  const loadScript = useCallback(async () => {
    setIsLoading(true)
    try {
      const res = await getCrawlerScript(companyId)
      if (res.data) {
        setCode(res.data.code)
        setOriginalCode(res.data.code)
        setUpdatedAt(res.data.updated_at)
      } else {
        setCode("")
        setOriginalCode("")
        setUpdatedAt(null)
      }
    } catch {
      /* ignore */
    } finally {
      setIsLoading(false)
    }
  }, [companyId])

  useEffect(() => {
    if (open) loadScript()
  }, [open, loadScript])

  // Close on Escape
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [open, onClose])

  const handleSave = async () => {
    if (!code.trim()) return
    setIsSaving(true)
    try {
      await saveCrawlerScript(companyId, code)
      setOriginalCode(code)
      setUpdatedAt(new Date().toISOString())
    } catch (err: any) {
      alert(err.message || "保存失败")
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm("确定删除已缓存的爬虫代码？下次爬取将重新生成。")) return
    try {
      await deleteCrawlerScript(companyId)
      setCode("")
      setOriginalCode("")
      setUpdatedAt(null)
    } catch (err: any) {
      alert(err.message || "删除失败")
    }
  }

  const hasChanges = code !== originalCode
  const hasCode = originalCode.length > 0

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

      {/* Dialog */}
      <div className="relative w-[90vw] max-w-4xl h-[80vh] bg-neutral-950 border border-neutral-700 rounded-xl shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-neutral-800 shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <Code2 className="size-4 text-blue-400 shrink-0" />
            <span className="text-sm text-text-primary font-medium truncate">
              {companyName} — 爬虫代码
            </span>
            {hasCode && updatedAt && (
              <span className="text-xs text-neutral-500 shrink-0">
                更新于 {new Date(updatedAt).toLocaleString("zh-CN")}
              </span>
            )}
            {hasChanges && (
              <span className="text-xs text-yellow-500 shrink-0">未保存</span>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {hasCode && (
              <Button
                variant="ghost"
                size="xs"
                onClick={handleDelete}
                className="text-red-400/70 hover:text-red-400 hover:bg-red-500/10"
              >
                <Trash2 className="size-3.5 mr-1" />
                删除
              </Button>
            )}
            <Button
              size="xs"
              onClick={handleSave}
              disabled={!hasChanges || isSaving || !code.trim()}
              className="bg-green-600 text-white hover:bg-green-500 disabled:opacity-30"
            >
              {isSaving ? <Loader2 className="size-3.5 mr-1 animate-spin" /> : <Save className="size-3.5 mr-1" />}
              保存
            </Button>
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={onClose}
              className="text-neutral-500 hover:text-neutral-300 ml-1"
            >
              <X className="size-4" />
            </Button>
          </div>
        </div>

        {/* Editor */}
        {isLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="size-5 animate-spin text-neutral-500" />
          </div>
        ) : (
          <div className="flex-1 overflow-hidden">
            <Editor
              height="100%"
              language="python"
              theme="vs-dark"
              value={code}
              onChange={(val) => setCode(val ?? "")}
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                lineNumbers: "on",
                scrollBeyondLastLine: false,
                wordWrap: "on",
                tabSize: 4,
                padding: { top: 12 },
                renderLineHighlight: "none",
              }}
            />
          </div>
        )}

        {/* Footer hint */}
        {!hasCode && !isLoading && (
          <div className="px-5 py-3 border-t border-neutral-800 text-xs text-neutral-500 shrink-0">
            暂无缓存代码。首次爬取成功后将自动缓存，或手动粘贴代码后保存。
          </div>
        )}
      </div>
    </div>
  )
}
