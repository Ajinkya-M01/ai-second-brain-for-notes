import React, { useState } from 'react'
import { AlertTriangle, Loader2, X } from 'lucide-react'
import { Note } from '../types/note'

interface DeleteNoteModalProps {
  isOpen: boolean
  note: Note | null
  onClose: () => void
  onConfirm: (id: string) => Promise<void>
}

export const DeleteNoteModal: React.FC<DeleteNoteModalProps> = ({
  isOpen,
  note,
  onClose,
  onConfirm,
}) => {
  const [isDeleting, setIsDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!isOpen || !note) return null

  const handleDelete = async () => {
    setIsDeleting(true)
    setError(null)
    try {
      await onConfirm(note.id)
      onClose()
    } catch (err: any) {
      setError(err?.detail || err?.message || 'Failed to delete note.')
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs animate-in fade-in duration-150"
    >
      <div className="relative w-full max-w-md rounded-2xl border border-rose-500/30 bg-[#11151D] p-6 shadow-2xl shadow-black/80">
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div className="flex-1">
            <h2 id="delete-dialog-title" className="text-base font-semibold text-white">
              Delete Note
            </h2>
            <p className="mt-1.5 text-xs text-[#94A3B8] leading-relaxed">
              Are you sure you want to permanently delete <span className="font-semibold text-white">"{note.title}"</span>? All content, metadata, and tags will be removed from SQLite.
            </p>
          </div>
          <button
            onClick={onClose}
            disabled={isDeleting}
            className="p-1 text-[#94A3B8] hover:text-white"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {error && (
          <div role="alert" className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-2.5 text-xs text-rose-300">
            {error}
          </div>
        )}

        <div className="mt-6 flex items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={onClose}
            disabled={isDeleting}
            className="rounded-xl border border-[#1F2633] bg-[#171C26] px-4 py-2 text-xs font-medium text-[#94A3B8] hover:bg-[#1E2433] hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={isDeleting}
            className="flex items-center gap-1.5 rounded-xl bg-rose-600 px-4 py-2 text-xs font-medium text-white shadow-md shadow-rose-950/50 hover:bg-rose-500 transition-colors disabled:opacity-50"
          >
            {isDeleting ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Deleting...</span>
              </>
            ) : (
              <span>Delete Note</span>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
