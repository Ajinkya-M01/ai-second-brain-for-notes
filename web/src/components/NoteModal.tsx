import React, { useState, useEffect } from 'react'
import { X, Loader2, AlertCircle, Tag as TagIcon } from 'lucide-react'
import { Note, NoteCreateInput } from '../types/note'

interface NoteModalProps {
  isOpen: boolean
  note?: Note | null
  onClose: () => void
  onSave: (data: NoteCreateInput) => Promise<void>
}

export const NoteModal: React.FC<NoteModalProps> = ({
  isOpen,
  note,
  onClose,
  onSave,
}) => {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [tagInput, setTagInput] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [validationError, setValidationError] = useState<string | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const isEdit = Boolean(note)

  useEffect(() => {
    if (note) {
      setTitle(note.title || '')
      setContent(note.content || '')
      setTags(note.tags || [])
    } else {
      setTitle('')
      setContent('')
      setTags([])
    }
    setTagInput('')
    setValidationError(null)
    setApiError(null)
  }, [note, isOpen])

  if (!isOpen) return null

  const handleAddTag = () => {
    const trimmed = tagInput.trim().toLowerCase()
    if (!trimmed) return
    if (!tags.includes(trimmed)) {
      setTags([...tags, trimmed])
    }
    setTagInput('')
  }

  const handleRemoveTag = (tagToRemove: string) => {
    setTags(tags.filter((t) => t !== tagToRemove))
  }

  const handleKeyDownTag = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      handleAddTag()
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setValidationError(null)
    setApiError(null)

    const trimmedTitle = title.trim()
    if (!trimmedTitle) {
      setValidationError('Please enter a note title.')
      return
    }

    if (!content.trim()) {
      setValidationError('Note content cannot be empty.')
      return
    }

    // Include any pending tag typed in the tagInput
    let finalTags = [...tags]
    if (tagInput.trim()) {
      const extra = tagInput.trim().toLowerCase()
      if (!finalTags.includes(extra)) {
        finalTags.push(extra)
      }
    }

    setIsSubmitting(true)
    try {
      await onSave({
        title: trimmedTitle,
        content: content,
        tags: finalTags,
      })
      onClose()
    } catch (err: any) {
      setApiError(err?.detail || err?.message || 'Failed to save note.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const wordCount = content.trim() ? content.trim().split(/\s+/).length : 0

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="note-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs animate-in fade-in duration-150"
    >
      <div className="relative w-full max-w-2xl rounded-2xl border border-[#2D3748] bg-[#11151D] p-6 shadow-2xl shadow-black/80 flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[#1F2633]">
          <div>
            <h2 id="note-modal-title" className="text-base font-semibold text-white tracking-tight">
              {isEdit ? 'Edit Note' : 'Create New Note'}
            </h2>
            <p className="text-xs text-[#94A3B8]">
              {isEdit ? 'Update your note content and tags' : 'Store a new markdown or text note in your second brain'}
            </p>
          </div>
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="rounded-lg p-1 text-[#94A3B8] hover:bg-[#171C26] hover:text-white transition-colors"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="flex flex-col flex-1 overflow-hidden pt-4 space-y-4">
          {/* Error Banner */}
          {(validationError || apiError) && (
            <div
              role="alert"
              className="flex items-center gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300"
            >
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
              <span>{validationError || apiError}</span>
            </div>
          )}

          {/* Title Field */}
          <div>
            <label htmlFor="note-title" className="block text-xs font-medium text-[#E2E8F0] mb-1">
              Title <span className="text-purple-400">*</span>
            </label>
            <input
              id="note-title"
              type="text"
              placeholder="e.g. Distributed Consensus in Raft"
              value={title}
              onChange={(e) => {
                setTitle(e.target.value)
                if (validationError) setValidationError(null)
              }}
              disabled={isSubmitting}
              autoFocus
              className="w-full rounded-xl border border-[#1F2633] bg-[#171C26] px-3.5 py-2 text-sm text-white placeholder-[#64748B] focus:border-[#8B5CF6] focus:outline-hidden focus:ring-1 focus:ring-[#8B5CF6]/50 transition-all"
            />
          </div>

          {/* Tags Field */}
          <div>
            <label htmlFor="note-tags-input" className="block text-xs font-medium text-[#E2E8F0] mb-1">
              Tags
            </label>
            <div className="flex flex-wrap items-center gap-1.5 rounded-xl border border-[#1F2633] bg-[#171C26] p-2 min-h-[42px] focus-within:border-[#8B5CF6] focus-within:ring-1 focus-within:ring-[#8B5CF6]/50">
              {tags.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-1 rounded-md bg-[#8B5CF6]/20 border border-[#8B5CF6]/30 px-2 py-0.5 text-xs font-mono text-[#A78BFA]"
                >
                  #{tag}
                  <button
                    type="button"
                    onClick={() => handleRemoveTag(tag)}
                    className="hover:text-white transition-colors"
                    aria-label={`Remove tag ${tag}`}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
              <div className="flex-1 flex items-center min-w-[120px]">
                <TagIcon className="h-3.5 w-3.5 text-[#64748B] ml-1 mr-1.5" />
                <input
                  id="note-tags-input"
                  type="text"
                  placeholder={tags.length === 0 ? 'Type tag and press Enter or comma...' : 'Add more...'}
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={handleKeyDownTag}
                  onBlur={handleAddTag}
                  disabled={isSubmitting}
                  className="w-full bg-transparent text-xs text-white placeholder-[#64748B] focus:outline-hidden"
                />
              </div>
            </div>
          </div>

          {/* Content Field */}
          <div className="flex-1 flex flex-col min-h-0">
            <div className="flex items-center justify-between mb-1">
              <label htmlFor="note-content" className="block text-xs font-medium text-[#E2E8F0]">
                Content (Markdown supported) <span className="text-purple-400">*</span>
              </label>
              <span className="text-[11px] font-mono text-[#64748B]">
                {wordCount} {wordCount === 1 ? 'word' : 'words'}
              </span>
            </div>
            <textarea
              id="note-content"
              rows={8}
              placeholder="Write your note markdown, ideas, key takeaways, code snippets..."
              value={content}
              onChange={(e) => {
                setContent(e.target.value)
                if (validationError) setValidationError(null)
              }}
              disabled={isSubmitting}
              className="w-full flex-1 resize-y min-h-[160px] rounded-xl border border-[#1F2633] bg-[#171C26] p-3 text-sm text-[#F3F4F6] placeholder-[#64748B] font-mono leading-relaxed focus:border-[#8B5CF6] focus:outline-hidden focus:ring-1 focus:ring-[#8B5CF6]/50 transition-all"
            />
          </div>

          {/* Modal Footer Actions */}
          <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-[#1F2633]">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="rounded-xl border border-[#1F2633] bg-[#171C26] px-4 py-2 text-xs font-medium text-[#94A3B8] hover:bg-[#1E2433] hover:text-white transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center gap-1.5 rounded-xl bg-[#8B5CF6] px-4 py-2 text-xs font-medium text-white shadow-md shadow-purple-900/40 hover:bg-[#7C3AED] transition-colors disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <span>{isEdit ? 'Save Changes' : 'Create Note'}</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
