import React, { useState, useRef } from 'react'
import { X, Upload, FileText, Loader2, AlertCircle, Info } from 'lucide-react'
import { Note } from '../types/note'
import { notesApi } from '../lib/api'

interface UploadPdfModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: (source: Note) => void
}

export const UploadPdfModal: React.FC<UploadPdfModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [file, setFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  if (!isOpen) return null

  const handleFileChange = (selectedFile: File | null) => {
    setError(null)
    if (!selectedFile) {
      setFile(null)
      return
    }

    if (!selectedFile.name.toLowerCase().endsWith('.pdf')) {
      setError('Please select a valid PDF file with a .pdf extension.')
      setFile(null)
      return
    }

    if (selectedFile.size === 0) {
      setError('Selected file is empty (0 bytes).')
      setFile(null)
      return
    }

    // 10MB client pre-check
    if (selectedFile.size > 10 * 1024 * 1024) {
      setError('File size exceeds the 10 MB limit.')
      setFile(null)
      return
    }

    setFile(selectedFile)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileChange(e.dataTransfer.files[0])
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) {
      setError('Please select a PDF file to upload.')
      return
    }

    setIsUploading(true)
    setError(null)

    try {
      const source = await notesApi.uploadDocument(file)
      onSuccess(source)
      onClose()
    } catch (err: any) {
      setError(err?.detail || err?.message || 'Failed to upload and extract PDF.')
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs animate-in fade-in duration-150"
    >
      <div className="relative w-full max-w-lg rounded-2xl border border-[#2D3748] bg-[#11151D] p-6 shadow-2xl shadow-black/80 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[#1F2633]">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-cyan-500/10 text-[#06B6D4] border border-cyan-500/20">
              <Upload className="h-5 w-5" />
            </div>
            <div>
              <h2 id="upload-modal-title" className="text-base font-semibold text-white tracking-tight">
                Upload PDF Document
              </h2>
              <p className="text-xs text-[#94A3B8]">Extract selectable text and page references</p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isUploading}
            className="rounded-lg p-1 text-[#94A3B8] hover:text-white hover:bg-[#171C26] transition-colors"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="pt-4 space-y-4">
          {/* Error Banner */}
          {error && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300 leading-relaxed"
            >
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-400 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Drag & Drop Area */}
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => fileInputRef.current?.click()}
            className={`flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-6 text-center cursor-pointer transition-all ${
              isDragging
                ? 'border-[#06B6D4] bg-cyan-950/20'
                : file
                ? 'border-[#06B6D4]/50 bg-[#171C26]'
                : 'border-[#1F2633] bg-[#171C26]/50 hover:border-[#2D3748] hover:bg-[#171C26]'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              className="hidden"
              onChange={(e) => handleFileChange(e.target.files?.[0] || null)}
              disabled={isUploading}
            />

            {file ? (
              <div className="flex flex-col items-center gap-2">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-cyan-500/10 text-[#06B6D4] border border-cyan-500/30">
                  <FileText className="h-6 w-6" />
                </div>
                <div className="max-w-[320px] truncate">
                  <span className="block text-sm font-semibold text-white truncate">{file.name}</span>
                  <span className="block text-xs text-[#94A3B8] font-mono">
                    {(file.size / (1024 * 1024)).toFixed(2)} MB • Ready to ingest
                  </span>
                </div>
                <span className="text-[11px] text-[#06B6D4] hover:underline mt-1">
                  Click to choose a different file
                </span>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#1E2433] text-[#94A3B8]">
                  <Upload className="h-6 w-6 text-[#06B6D4]" />
                </div>
                <div>
                  <span className="text-sm font-medium text-white">Click to browse or drop PDF here</span>
                  <p className="mt-1 text-xs text-[#64748B]">Maximum 10 MB • Up to 100 pages</p>
                </div>
              </div>
            )}
          </div>

          {/* Info callout */}
          <div className="flex items-start gap-2 rounded-xl border border-[#1F2633] bg-[#0E1118] p-3 text-xs text-[#94A3B8]">
            <Info className="h-4 w-4 text-[#06B6D4] shrink-0 mt-0.5" />
            <p className="leading-relaxed">
              <strong className="text-[#E2E8F0]">Selectable text PDFs only:</strong> Text will be extracted page by page using <code className="text-cyan-300 font-mono">pypdf</code>. Scanned image-only PDFs requiring OCR are not supported in the MVP.
            </p>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-[#1F2633]">
            <button
              type="button"
              onClick={onClose}
              disabled={isUploading}
              className="rounded-xl border border-[#1F2633] bg-[#171C26] px-4 py-2 text-xs font-medium text-[#94A3B8] hover:bg-[#1E2433] hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!file || isUploading}
              className="flex items-center gap-1.5 rounded-xl bg-[#06B6D4] px-4 py-2 text-xs font-medium text-white shadow-md shadow-cyan-900/30 hover:bg-[#0891B2] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isUploading ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Extracting Text...</span>
                </>
              ) : (
                <span>Upload & Extract</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
