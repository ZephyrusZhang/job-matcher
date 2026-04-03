"use client"

import { useState, useRef, useCallback } from "react"
import { FileText, Upload, CheckCircle, Loader2 } from "lucide-react"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import type { ResumeInfo } from "@/types/resume"
import { cn } from "@/lib/utils"

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:3001"

interface ResumeUploaderProps {
  resume: ResumeInfo | null
  onUploadSuccess: (resume: ResumeInfo) => void
}

export function ResumeUploader({ resume, onUploadSuccess }: ResumeUploaderProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const uploadFile = useCallback(
    async (file: File) => {
      setIsUploading(true)
      try {
        const formData = new FormData()
        formData.append("file", file)
        const res = await fetch(`${API_BASE}/api/resume/upload`, {
          method: "POST",
          body: formData,
        })
        const data = await res.json()
        if (data.success) {
          onUploadSuccess(data.data)
        }
      } finally {
        setIsUploading(false)
      }
    },
    [onUploadSuccess]
  )

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) uploadFile(file)
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) uploadFile(file)
    e.target.value = ""
  }

  const handleReupload = () => {
    setShowConfirm(true)
  }

  const confirmReupload = () => {
    setShowConfirm(false)
    fileInputRef.current?.click()
  }

  if (isUploading) {
    return (
      <div className="flex items-center gap-3 bg-bg-secondary border border-border-default rounded-[var(--radius)] p-4">
        <Loader2 className="h-5 w-5 text-zinc-400 animate-spin" />
        <span className="text-sm text-text-primary">上传中...</span>
        <input ref={fileInputRef} type="file" accept=".pdf,.docx" className="hidden" onChange={handleFileSelect} />
      </div>
    )
  }

  if (resume) {
    return (
      <>
        <div className="bg-bg-secondary border border-border-default rounded-[var(--radius)] p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span className="text-sm text-text-primary">{resume.filename}</span>
            </div>
            <button
              onClick={handleReupload}
              className="text-zinc-400 text-sm cursor-pointer hover:text-text-primary hover:underline"
            >
              重新上传
            </button>
          </div>
          {resume.parsed.skills.length > 0 && (
            <p className="text-xs text-text-muted mt-2">
              技能: {resume.parsed.skills.join(", ")}
            </p>
          )}
        </div>
        <input ref={fileInputRef} type="file" accept=".pdf,.docx" className="hidden" onChange={handleFileSelect} />

        <AlertDialog open={showConfirm} onOpenChange={setShowConfirm}>
          <AlertDialogContent className="bg-bg-secondary border-border-default">
            <AlertDialogHeader>
              <AlertDialogTitle className="text-text-primary">确认重新上传简历？</AlertDialogTitle>
              <AlertDialogDescription className="text-text-secondary">
                上传新简历将清空所有已生成的报告和对话记录
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel className="border-border-default text-text-primary">取消</AlertDialogCancel>
              <AlertDialogAction
                onClick={confirmReupload}
                className="bg-text-primary text-bg-primary hover:bg-zinc-300"
              >
                确认上传
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </>
    )
  }

  return (
    <>
      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={cn(
          "border-2 border-dashed rounded-[var(--radius)] p-8 text-center cursor-pointer transition-all",
          isDragging
            ? "border-zinc-500 bg-zinc-800/50"
            : "border-border-default bg-transparent hover:border-zinc-600"
        )}
      >
        {isDragging ? (
          <div className="flex flex-col items-center gap-2">
            <Upload className="h-8 w-8 text-zinc-400" />
            <p className="text-sm text-zinc-300">松开以上传文件</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <FileText className="h-8 w-8 text-text-muted" />
            <p className="text-sm text-text-secondary">
              拖拽上传或
              <span className="text-text-primary cursor-pointer underline underline-offset-2">点击选择文件</span>
            </p>
            <p className="text-xs text-text-muted">支持 PDF / DOCX，最大 10MB</p>
          </div>
        )}
      </div>
      <input ref={fileInputRef} type="file" accept=".pdf,.docx" className="hidden" onChange={handleFileSelect} />
    </>
  )
}
