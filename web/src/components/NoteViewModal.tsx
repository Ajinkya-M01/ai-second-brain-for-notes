import React from 'react'
import { X, Edit3, Trash2, Calendar, FileText, Hash, Clock, Check, Copy } from 'lucide-react'
import { Note } from '../types/note'

interface NoteViewModalProps {
  isOpen: boolean
  note: Note | null
  onClose: () => void
  onEdit: (note: Note) => void
  onDelete: (note: Note) => void
}

export const NoteViewModal: React.FC<NoteViewModalProps> = ({
  isOpen,
  note,
  onClose,
  onEdit,
  onDelete,
}) => {
  const [copied, setCopied] = React.useState(false)

  if (!isOpen || !note) return null

  const handleCopy = () => {
    if (note.content) {
      navigator.clipboard.writeText(note.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const wordCount = note.content ? note.content.trim().split(/\s+/).length : 0

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="note-view-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs animate-in fade-in duration-150"
    >
      <div className="relative w-full max-w-2xl rounded-2xl border border-[#2D3748] bg-[#11151D] p-6 shadow-2xl shadow-black/80 flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-start justify-between pb-4 border-b border-[#1F2633] gap-3">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span
                className={`rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider border ${
                  note.kind === 'pdf'
                    ? 'bg-cyan-500/10 text-[#06B6D4] border-cyan-500/20'
                    : 'bg-purple-500/10 text-[#A78BFA] border-purple-500/20'
                }`}
              >
                {note.kind === 'pdf' ? 'PDF Document' : 'Note'}
              </span>
              <span className="text-[11px] font-mono text-[#64748B]">
                {note.status}
              </span>
              {note.original_filename && (
                <span className="text-[11px] font-mono text-[#94A3B8] truncate max-w-[200px]" title={note.original_filename}>
                  ({note.original_filename})
                </span>
              )}
            </div>
            <h2 id="note-view-title" className="mt-1.5 text-lg font-semibold text-white tracking-tight leading-snug">
              {note.title}
            </h2>
          </div>
          <div className="flex items-center gap-1.5">
            {note.kind === 'note' && (
              <button
                onClick={() => {
                  onClose()
                  onEdit(note)
                }}
                className="flex items-center gap-1 rounded-lg border border-[#1F2633] bg-[#171C26] px-2.5 py-1.5 text-xs text-[#E2E8F0] hover:bg-[#1E2433] hover:text-white transition-colors"
                title="Edit Note"
              >
                <Edit3 className="h-3.5 w-3.5 text-[#8B5CF6]" />
                <span>Edit</span>
              </button>
            )}
            <button
              onClick={() => {
                onClose()
                onDelete(note)
              }}
              className="flex items-center gap-1 rounded-lg border border-rose-500/20 bg-rose-500/10 px-2.5 py-1.5 text-xs text-rose-300 hover:bg-rose-500/20 transition-colors"
              title="Delete Note"
            >
              <Trash2 className="h-3.5 w-3.5" />
              <span>Delete</span>
            </button>
            <button
              onClick={onClose}
              className="rounded-lg p-1 text-[#94A3B8] hover:text-white hover:bg-[#171C26] transition-colors ml-1"
              aria-label="Close"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Tags row */}
        {note.tags && note.tags.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 pt-3">
            {note.tags.map((tag) => (
              <span
                key={tag}
                className="rounded-md bg-[#171C26] px-2 py-0.5 text-xs font-mono text-[#A78BFA] border border-[#1F2633]"
              >
                #{tag}
              </span>
            ))}
          </div>
        )}

        {/* Content body */}
        <div className="flex-1 overflow-y-auto py-4">
          <div className="rounded-xl border border-[#1F2633] bg-[#0E1118] p-4 text-sm text-[#F3F4F6] font-mono leading-relaxed whitespace-pre-wrap select-text">
            {note.content || <span className="text-[#64748B] italic">No content.</span>}
          </div>
        </div>

        {/* Metadata Footer */}
        <div className="pt-3 border-t border-[#1F2633] flex flex-wrap items-center justify-between text-[11px] text-[#64748B] gap-2">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1" title="Word count">
              <FileText className="h-3 w-3" />
              {wordCount} words ({note.size_bytes} B)
            </span>
            <span className="flex items-center gap-1" title="Created date">
              <Calendar className="h-3 w-3" />
              {new Date(note.created_at).toLocaleDateString()}
            </span>
            <span className="flex items-center gap-1" title="Last updated">
              <Clock className="h-3 w-3" />
              {new Date(note.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1 font-mono text-[10px]" title={`SHA-256: ${note.content_sha256}`}>
              <Hash className="h-3 w-3" />
              {note.content_sha256.substring(0, 8)}...
            </span>
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 rounded-md bg-[#171C26] px-2 py-1 text-[11px] text-[#94A3B8] hover:text-white border border-[#1F2633] transition-colors"
            >
              {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
              <span>{copied ? 'Copied' : 'Copy'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
