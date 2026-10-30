import React, { useEffect } from 'react'
import { X, BookOpen, FileText, Hash, ExternalLink } from 'lucide-react'
import { Citation } from '../types/chat'

interface CitationModalProps {
  isOpen: boolean
  citation: Citation | null
  onClose: () => void
  onViewSource?: (sourceId: string) => void
}

export const CitationModal: React.FC<CitationModalProps> = ({
  isOpen,
  citation,
  onClose,
  onViewSource,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown)
    }
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen || !citation) return null

  const isPdf = citation.page_number !== null && citation.page_number !== undefined

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="citation-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-xs animate-in fade-in duration-150"
    >
      <div className="relative w-full max-w-xl rounded-2xl border border-[#2D3748] bg-[#11151D] p-6 shadow-2xl shadow-black/90 flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-start justify-between pb-4 border-b border-[#1F2633] gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="rounded-md bg-purple-500/20 text-[#A78BFA] border border-purple-500/30 px-2 py-0.5 text-xs font-mono font-semibold">
                {citation.label}
              </span>
              <span
                className={`rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider border ${
                  isPdf
                    ? 'bg-cyan-500/10 text-[#06B6D4] border-cyan-500/20'
                    : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                }`}
              >
                {isPdf ? `PDF Page ${citation.page_number}` : 'Note'}
              </span>
            </div>
            <h2
              id="citation-modal-title"
              className="mt-2 text-base font-semibold text-white tracking-tight leading-snug truncate"
              title={citation.title}
            >
              {citation.title}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-[#94A3B8] hover:text-white hover:bg-[#171C26] transition-colors"
            aria-label="Close citation details"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content Body: Verified Evidence Excerpt */}
        <div className="flex-1 overflow-y-auto py-4 space-y-3">
          <div className="text-[11px] font-semibold text-[#64748B] uppercase tracking-wider flex items-center gap-1.5">
            <BookOpen className="h-3.5 w-3.5 text-[#8B5CF6]" />
            <span>Retrieved Evidence Excerpt</span>
          </div>
          <div className="rounded-xl border border-[#1F2633] bg-[#0E1118] p-4 text-xs text-[#E2E8F0] font-mono leading-relaxed whitespace-pre-wrap select-text">
            {citation.excerpt}
          </div>
        </div>

        {/* Metadata & Actions Footer */}
        <div className="pt-3 border-t border-[#1F2633] flex items-center justify-between text-[11px] text-[#64748B]">
          <div className="flex items-center gap-2 font-mono text-[10px] truncate max-w-[300px]">
            <Hash className="h-3 w-3 shrink-0" />
            <span className="truncate" title={`Chunk: ${citation.chunk_id}`}>
              chunk:{citation.chunk_id.substring(0, 8)}...
            </span>
          </div>

          <div className="flex items-center gap-2">
            {onViewSource && (
              <button
                onClick={() => {
                  onClose()
                  onViewSource(citation.source_id)
                }}
                className="flex items-center gap-1 rounded-lg bg-[#171C26] hover:bg-[#1E2433] text-[#A78BFA] border border-[#2D3748] px-3 py-1.5 text-xs font-medium transition-colors"
              >
                <FileText className="h-3.5 w-3.5" />
                <span>View Full Source</span>
                <ExternalLink className="h-3 w-3 ml-0.5 opacity-60" />
              </button>
            )}
            <button
              onClick={onClose}
              className="rounded-lg bg-[#8B5CF6] hover:bg-[#7C3AED] text-white px-3.5 py-1.5 text-xs font-medium transition-colors"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

