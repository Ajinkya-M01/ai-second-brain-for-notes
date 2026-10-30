import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Brain,
  Search,
  Plus,
  Upload,
  FileText,
  Tag as TagIcon,
  MessageSquare,
  Server,
  Layers,
  Menu,
  X,
  RefreshCw,
  Edit3,
  Trash2,
  AlertCircle,
  CheckCircle2,
  Calendar,
} from 'lucide-react'
import { Note, NoteCreateInput } from './types/note'
import { Citation } from './types/chat'
import { notesApi } from './lib/api'
import { NoteModal } from './components/NoteModal'
import { DeleteNoteModal } from './components/DeleteNoteModal'
import { NoteViewModal } from './components/NoteViewModal'
import { UploadPdfModal } from './components/UploadPdfModal'
import { CitationModal } from './components/CitationModal'
import { ChatPanel } from './components/ChatPanel'

interface HealthState {
  status: 'checking' | 'connected' | 'disconnected'
  message?: string
}

interface ToastNotification {
  id: string
  type: 'success' | 'error'
  message: string
}

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [mobileTab, setMobileTab] = useState<'library' | 'chat'>('library')
  const [health, setHealth] = useState<HealthState>({ status: 'checking' })

  // Library & Notes State
  const [notes, setNotes] = useState<Note[]>([])
  const [totalNotes, setTotalNotes] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedTag, setSelectedTag] = useState<string | null>(null)
  const [activeFilter, setActiveFilter] = useState<'all' | 'notes'>('all')

  // Modals
  const [isNoteModalOpen, setIsNoteModalOpen] = useState(false)
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false)
  const [editingNote, setEditingNote] = useState<Note | null>(null)
  const [viewingNote, setViewingNote] = useState<Note | null>(null)
  const [deletingNote, setDeletingNote] = useState<Note | null>(null)
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null)

  // Toast Notifications
  const [toasts, setToasts] = useState<ToastNotification[]>([])

  const addToast = (type: 'success' | 'error', message: string) => {
    const id = Math.random().toString(36).substring(2, 9)
    setToasts((prev) => [...prev, { id, type, message }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 3500)
  }

  // Health probe
  const checkHealth = useCallback(async () => {
    setHealth({ status: 'checking' })
    try {
      const data = await notesApi.checkHealth()
      if (data.status === 'ok') {
        setHealth({ status: 'connected', message: 'Liveness OK' })
        return
      }
      setHealth({ status: 'disconnected', message: 'Unexpected response' })
    } catch {
      setHealth({ status: 'disconnected', message: 'Backend unreachable' })
    }
  }, [])

  // Fetch Notes
  const fetchNotes = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await notesApi.listNotes({
        q: searchQuery.trim() || undefined,
        tag: selectedTag || undefined,
      })
      setNotes(response.items)
      setTotalNotes(response.total)
    } catch (err: any) {
      setError(err?.detail || err?.message || 'Failed to fetch notes from backend.')
    } finally {
      setIsLoading(false)
    }
  }, [searchQuery, selectedTag])

  // Initial loads
  useEffect(() => {
    checkHealth()
    const timer = setInterval(checkHealth, 30000)
    return () => clearInterval(timer)
  }, [checkHealth])

  useEffect(() => {
    fetchNotes()
  }, [fetchNotes])

  // Compute dynamic tags from fetched notes
  const tagCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const note of notes) {
      if (note.tags) {
        for (const tag of note.tags) {
          counts[tag] = (counts[tag] || 0) + 1
        }
      }
    }
    return Object.entries(counts).sort((a, b) => b[1] - a[1])
  }, [notes])

  // Handle Note Create / Update Save
  const handleSaveNote = async (input: NoteCreateInput) => {
    if (editingNote) {
      const updated = await notesApi.updateNote(editingNote.id, input)
      setNotes((prev) => prev.map((n) => (n.id === updated.id ? updated : n)))
      addToast('success', `Note "${updated.title}" updated successfully.`)
    } else {
      const created = await notesApi.createNote(input)
      setNotes((prev) => [created, ...prev])
      setTotalNotes((prev) => prev + 1)
      addToast('success', `Note "${created.title}" created successfully.`)
    }
  }

  // Handle Note Deletion
  const handleDeleteNote = async (id: string) => {
    await notesApi.deleteNote(id)
    setNotes((prev) => prev.filter((n) => n.id !== id))
    setTotalNotes((prev) => Math.max(0, prev - 1))
    if (viewingNote?.id === id) setViewingNote(null)
    addToast('success', 'Note permanently deleted from database.')
  }

  // Handle successful PDF upload — prepend source and toast
  const handleUploadSuccess = (source: Note) => {
    setNotes((prev) => [source, ...prev])
    setTotalNotes((prev) => prev + 1)
    addToast('success', `PDF "${source.title}" uploaded and indexed successfully.`)
    fetchNotes()
  }

  const openCreateModal = () => {
    setEditingNote(null)
    setIsNoteModalOpen(true)
  }

  const openEditModal = (note: Note) => {
    setEditingNote(note)
    setIsNoteModalOpen(true)
  }

  const handleViewSourceById = async (sourceId: string) => {
    const found = notes.find((n) => n.id === sourceId)
    if (found) {
      setViewingNote(found)
      return
    }
    try {
      const fetched = await notesApi.getNote(sourceId)
      setViewingNote(fetched)
    } catch {
      addToast('error', 'Unable to load source document.')
    }
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#0B0D12] text-[#F3F4F6]">
      {/* Toast Notification Stack */}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-center gap-2.5 rounded-xl border p-3.5 shadow-xl text-xs backdrop-blur-md transition-all animate-in slide-in-from-top-2 ${
              toast.type === 'success'
                ? 'border-emerald-500/30 bg-[#11151D]/95 text-emerald-300 shadow-emerald-950/20'
                : 'border-rose-500/30 bg-[#11151D]/95 text-rose-300 shadow-rose-950/20'
            }`}
          >
            {toast.type === 'success' ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
            ) : (
              <AlertCircle className="h-4 w-4 text-rose-400 shrink-0" />
            )}
            <span className="font-medium">{toast.message}</span>
          </div>
        ))}
      </div>

      {/* Mobile Backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-xs md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* 240px Left Rail / Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-[240px] flex-col border-r border-[#1F2633] bg-[#11151D] transition-transform duration-200 ease-in-out md:static md:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand Header */}
        <div className="flex h-16 items-center justify-between border-b border-[#1F2633] px-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-[#8B5CF6] to-[#6D28D9] text-white shadow-lg shadow-purple-950/40">
              <Brain className="h-5 w-5" />
            </div>
            <div>
              <span className="font-semibold tracking-tight text-white text-sm">Second Brain</span>
              <span className="block text-[11px] text-[#94A3B8] font-mono">v0.1.0 • Grounded Q&A</span>
            </div>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="p-1.5 text-[#94A3B8] hover:text-white md:hidden"
            aria-label="Close sidebar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Navigation Sections */}
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
          <div>
            <div className="px-3 pb-2 text-[10px] font-semibold tracking-wider text-[#64748B] uppercase">
              Workspace
            </div>
            <nav className="space-y-1">
              <button
                onClick={() => {
                  setMobileTab('library')
                  setSelectedTag(null)
                  setSearchQuery('')
                }}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  mobileTab === 'library' && !selectedTag
                    ? 'bg-[#171C26] text-white border border-[#262E3D]'
                    : 'text-[#94A3B8] hover:bg-[#171C26]/60 hover:text-white'
                }`}
              >
                <Layers className="h-4 w-4 text-[#8B5CF6]" />
                <span>Library</span>
                <span className="ml-auto rounded-full bg-[#1E2433] px-2 py-0.5 text-[10px] font-mono text-[#94A3B8]">
                  {totalNotes}
                </span>
              </button>
              <button
                onClick={openCreateModal}
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-[#94A3B8] hover:bg-[#171C26]/60 hover:text-white transition-colors"
              >
                <Plus className="h-4 w-4 text-[#8B5CF6]" />
                <span>New Note</span>
              </button>
              <button
                onClick={() => setMobileTab('chat')}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  mobileTab === 'chat'
                    ? 'bg-[#171C26] text-white border border-[#262E3D]'
                    : 'text-[#94A3B8] hover:bg-[#171C26]/60 hover:text-white'
                }`}
              >
                <MessageSquare className="h-4 w-4 text-[#8B5CF6]" />
                <span>Ask Second Brain</span>
              </button>
            </nav>
          </div>

          {/* Dynamic Tags Filter */}
          <div>
            <div className="flex items-center justify-between px-3 pb-2">
              <span className="text-[10px] font-semibold tracking-wider text-[#64748B] uppercase">
                Tags & Taxonomies
              </span>
              {selectedTag && (
                <button
                  onClick={() => setSelectedTag(null)}
                  className="text-[10px] text-[#8B5CF6] hover:underline"
                >
                  Clear
                </button>
              )}
            </div>
            <div className="space-y-1">
              {tagCounts.length === 0 ? (
                <div className="px-3 py-2 text-xs text-[#64748B] italic">No tags yet</div>
              ) : (
                tagCounts.map(([tag, count]) => {
                  const isSelected = selectedTag === tag
                  return (
                    <button
                      key={tag}
                      onClick={() => {
                        setMobileTab('library')
                        setSelectedTag(isSelected ? null : tag)
                      }}
                      className={`flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-xs transition-colors ${
                        isSelected
                          ? 'bg-[#8B5CF6]/20 text-[#A78BFA] border border-[#8B5CF6]/40 font-medium'
                          : 'text-[#94A3B8] hover:bg-[#171C26]/40'
                      }`}
                    >
                      <TagIcon className={`h-3.5 w-3.5 ${isSelected ? 'text-[#8B5CF6]' : 'text-[#64748B]'}`} />
                      <span className="truncate">#{tag}</span>
                      <span className="ml-auto text-[10px] font-mono text-[#64748B]">{count}</span>
                    </button>
                  )
                })
              )}
            </div>
          </div>
        </div>

        {/* Backend Liveness Health Card */}
        <div className="border-t border-[#1F2633] p-3">
          <div className="rounded-xl border border-[#1F2633] bg-[#171C26] p-3 text-xs shadow-xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Server className="h-3.5 w-3.5 text-[#94A3B8]" />
                <span className="font-medium text-[#E2E8F0]">API & SQLite</span>
              </div>
              <button
                onClick={() => {
                  checkHealth()
                  fetchNotes()
                }}
                className="text-[#94A3B8] hover:text-white transition-colors p-1"
                title="Refresh health check and notes"
              >
                <RefreshCw
                  className={`h-3 w-3 ${health.status === 'checking' ? 'animate-spin text-[#8B5CF6]' : ''}`}
                />
              </button>
            </div>
            <div className="mt-2 flex items-center gap-2">
              <div
                className={`h-2 w-2 rounded-full ${
                  health.status === 'connected'
                    ? 'bg-emerald-400 shadow-xs shadow-emerald-400/50'
                    : health.status === 'checking'
                    ? 'bg-amber-400 animate-pulse'
                    : 'bg-rose-500'
                }`}
              />
              <span className="text-[11px] text-[#94A3B8] truncate">
                {health.status === 'connected'
                  ? 'Connected (GET /health 200)'
                  : health.status === 'checking'
                  ? 'Probing localhost:8000...'
                  : health.message || 'Offline'}
              </span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Container */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Compact Top Bar */}
        <header className="flex h-16 items-center justify-between border-b border-[#1F2633] bg-[#11151D]/90 px-4 md:px-6 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="p-1.5 text-[#94A3B8] hover:text-white md:hidden"
              aria-label="Open sidebar"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div>
              <h1 className="text-base font-semibold text-white tracking-tight">Library Workspace</h1>
              <p className="text-xs text-[#94A3B8] hidden sm:block">
                {selectedTag ? `Filtered by tag: #${selectedTag}` : 'Canonical notes & personal knowledge base'}
              </p>
            </div>
          </div>

          {/* Global Search Bar */}
          <div className="relative hidden w-72 md:block">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#64748B]" />
            <input
              type="text"
              placeholder="Search notes & content..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-lg border border-[#1F2633] bg-[#171C26] py-1.5 pl-9 pr-3 text-xs text-white placeholder-[#64748B] focus:border-[#8B5CF6] focus:outline-hidden focus:ring-1 focus:ring-[#8B5CF6]/50 transition-all"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#64748B] hover:text-white text-xs"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={openCreateModal}
              className="flex items-center gap-1.5 rounded-lg bg-[#8B5CF6] px-3.5 py-1.5 text-xs font-medium text-white shadow-md shadow-purple-900/30 hover:bg-[#7C3AED] transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>New Note</span>
            </button>
            <button
              id="upload-pdf-btn"
              onClick={() => setIsUploadModalOpen(true)}
              className="flex items-center gap-1.5 rounded-lg border border-[#1F2633] bg-[#171C26] px-3 py-1.5 text-xs font-medium text-[#94A3B8] hover:bg-[#1E2433] hover:text-white hover:border-[#2D3748] transition-colors"
              aria-label="Upload PDF document"
            >
              <Upload className="h-3.5 w-3.5 text-[#06B6D4]" />
              <span className="hidden sm:inline">Upload PDF</span>
            </button>
          </div>
        </header>

        {/* Mobile Tab Switcher */}
        <div className="flex border-b border-[#1F2633] bg-[#11151D] px-4 md:hidden">
          <button
            onClick={() => setMobileTab('library')}
            className={`flex-1 py-2.5 text-xs font-medium text-center border-b-2 transition-colors ${
              mobileTab === 'library'
                ? 'border-[#8B5CF6] text-white'
                : 'border-transparent text-[#94A3B8]'
            }`}
          >
            Library & Notes ({totalNotes})
          </button>
          <button
            onClick={() => setMobileTab('chat')}
            className={`flex-1 py-2.5 text-xs font-medium text-center border-b-2 transition-colors ${
              mobileTab === 'chat'
                ? 'border-[#8B5CF6] text-white'
                : 'border-transparent text-[#94A3B8]'
            }`}
          >
            Grounded Q&A
          </button>
        </div>

        {/* Workspace Split Layout */}
        <main className="flex flex-1 overflow-hidden">
          {/* Left Panel: Library & Content */}
          <section
            className={`flex-1 flex-col overflow-y-auto p-4 md:p-6 space-y-5 border-r border-[#1F2633] ${
              mobileTab === 'library' ? 'flex' : 'hidden md:flex'
            }`}
          >
            {/* Filter Pills & Mobile Search */}
            <div className="space-y-3">
              <div className="relative md:hidden">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#64748B]" />
                <input
                  type="text"
                  placeholder="Search notes..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full rounded-lg border border-[#1F2633] bg-[#171C26] py-1.5 pl-9 pr-3 text-xs text-white placeholder-[#64748B] focus:border-[#8B5CF6] focus:outline-hidden"
                />
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => setActiveFilter('all')}
                    className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                      activeFilter === 'all'
                        ? 'bg-[#8B5CF6]/20 text-[#A78BFA] border border-[#8B5CF6]/40'
                        : 'text-[#94A3B8] hover:bg-[#171C26]'
                    }`}
                  >
                    All Notes ({totalNotes})
                  </button>
                  {selectedTag && (
                    <span className="flex items-center gap-1 rounded-full bg-[#8B5CF6]/15 border border-[#8B5CF6]/30 px-2.5 py-0.5 text-xs font-mono text-[#A78BFA]">
                      #{selectedTag}
                      <button
                        onClick={() => setSelectedTag(null)}
                        className="hover:text-white ml-0.5"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  )}
                </div>
                <span className="text-[11px] font-mono text-[#64748B]">SQLite Backed</span>
              </div>
            </div>

            {/* Error State */}
            {error && (
              <div
                role="alert"
                className="flex items-start justify-between rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300"
              >
                <div className="flex items-center gap-2.5">
                  <AlertCircle className="h-5 w-5 text-rose-400 shrink-0" />
                  <div>
                    <span className="font-semibold block text-sm">Failed to load notes</span>
                    <span className="text-[#94A3B8]">{error}</span>
                  </div>
                </div>
                <button
                  onClick={fetchNotes}
                  className="rounded-lg bg-rose-600/40 border border-rose-500/40 px-3 py-1 text-xs text-white hover:bg-rose-600 transition-colors"
                >
                  Retry
                </button>
              </div>
            )}

            {/* Loading Shimmer Skeletons */}
            {isLoading && (
              <div data-testid="notes-loading-skeleton" className="grid gap-3.5">
                {[1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="rounded-xl border border-[#1F2633] bg-[#11151D] p-4 space-y-3 animate-pulse"
                  >
                    <div className="flex items-center justify-between">
                      <div className="h-4 w-48 rounded-md bg-[#1F2633]" />
                      <div className="h-4 w-12 rounded-md bg-[#1F2633]" />
                    </div>
                    <div className="space-y-1.5">
                      <div className="h-3 w-full rounded-md bg-[#171C26]" />
                      <div className="h-3 w-3/4 rounded-md bg-[#171C26]" />
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="h-4 w-16 rounded-md bg-[#171C26]" />
                      <div className="h-4 w-20 rounded-md bg-[#171C26]" />
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Empty State */}
            {!isLoading && !error && notes.length === 0 && (
              <div
                data-testid="notes-empty-state"
                className="rounded-2xl border border-dashed border-[#1F2633] bg-[#11151D]/40 p-8 text-center"
              >
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#171C26] text-[#8B5CF6] border border-[#1F2633]">
                  <FileText className="h-6 w-6" />
                </div>
                <h3 className="mt-3 text-sm font-semibold text-white">
                  {searchQuery || selectedTag ? 'No matching notes found' : 'Your library is empty'}
                </h3>
                <p className="mx-auto mt-1 max-w-sm text-xs text-[#94A3B8] leading-relaxed">
                  {searchQuery || selectedTag
                    ? 'Try clearing your search query or tag filter to view all notes.'
                    : 'Start organizing your thoughts, code snippets, research, and insights in your second brain.'}
                </p>
                <div className="mt-5">
                  {searchQuery || selectedTag ? (
                    <button
                      onClick={() => {
                        setSearchQuery('')
                        setSelectedTag(null)
                      }}
                      className="rounded-xl border border-[#1F2633] bg-[#171C26] px-4 py-2 text-xs font-medium text-[#E2E8F0] hover:bg-[#1E2433] hover:text-white transition-colors"
                    >
                      Clear Filters
                    </button>
                  ) : (
                    <button
                      onClick={openCreateModal}
                      className="inline-flex items-center gap-1.5 rounded-xl bg-[#8B5CF6] px-4 py-2 text-xs font-medium text-white shadow-md shadow-purple-900/40 hover:bg-[#7C3AED] transition-colors"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      <span>Create Your First Note</span>
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Notes List Cards */}
            {!isLoading && !error && notes.length > 0 && (
              <div data-testid="notes-list" className="grid gap-3.5">
                {notes.map((note) => {
                  const wordCount = note.content ? note.content.trim().split(/\s+/).length : 0
                  return (
                    <div
                      key={note.id}
                      onClick={() => setViewingNote(note)}
                      className="group relative rounded-xl border border-[#1F2633] bg-[#11151D] p-4 transition-all hover:border-[#2D3748] hover:bg-[#171C26]/50 cursor-pointer shadow-xs"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-2.5 flex-1 min-w-0">
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-purple-500/10 text-[#A78BFA] border border-purple-500/20">
                            <FileText className="h-4 w-4" />
                          </div>
                          <div className="truncate">
                            <h2 className="text-sm font-semibold text-white group-hover:text-[#A78BFA] transition-colors truncate">
                              {note.title}
                            </h2>
                            <div className="flex items-center gap-2 text-[11px] text-[#64748B]">
                              <span className="flex items-center gap-1">
                                <Calendar className="h-3 w-3" />
                                {new Date(note.updated_at).toLocaleDateString()}
                              </span>
                              <span>•</span>
                              <span>{wordCount} words</span>
                            </div>
                          </div>
                        </div>

                        {/* Card Hover Action Buttons */}
                        <div
                          className="flex items-center gap-1 opacity-80 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <button
                            onClick={() => openEditModal(note)}
                            className="rounded-lg p-1.5 text-[#94A3B8] hover:text-white hover:bg-[#1E2433] transition-colors"
                            title="Edit Note"
                            aria-label={`Edit ${note.title}`}
                          >
                            <Edit3 className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => setDeletingNote(note)}
                            className="rounded-lg p-1.5 text-[#94A3B8] hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                            title="Delete Note"
                            aria-label={`Delete ${note.title}`}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>

                      {/* Content Preview Snippet */}
                      <p className="mt-2 text-xs text-[#94A3B8] line-clamp-2 leading-relaxed">
                        {note.content || <span className="italic text-[#64748B]">Empty note</span>}
                      </p>

                      {/* Tags & Metadata Footer */}
                      <div className="mt-3 flex items-center justify-between pt-2 border-t border-[#1F2633]/50 text-[10px]">
                        <div className="flex flex-wrap items-center gap-1.5">
                          {note.tags && note.tags.length > 0 ? (
                            note.tags.map((tag) => (
                              <button
                                key={tag}
                                onClick={(e) => {
                                  e.stopPropagation()
                                  setSelectedTag(tag)
                                }}
                                className="inline-flex items-center rounded-md bg-[#171C26] px-2 py-0.5 font-mono text-[#A78BFA] border border-[#1F2633] hover:border-[#8B5CF6]/50 transition-colors"
                              >
                                #{tag}
                              </button>
                            ))
                          ) : (
                            <span className="text-[#64748B] italic">No tags</span>
                          )}
                        </div>
                        <span className="font-mono text-[#64748B] text-[10px]">
                          {note.content_sha256.substring(0, 6)}
                        </span>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </section>

          {/* Right Panel: Connected Grounded Chat & Citations */}
          <ChatPanel
            onCitationClick={(citation) => setActiveCitation(citation)}
            onViewSource={handleViewSourceById}
            className={`w-full md:w-[460px] lg:w-[500px] ${
              mobileTab === 'chat' ? 'flex' : 'hidden md:flex'
            }`}
          />
        </main>
      </div>

      {/* Note Create & Edit Modal */}
      <NoteModal
        isOpen={isNoteModalOpen}
        note={editingNote}
        onClose={() => setIsNoteModalOpen(false)}
        onSave={handleSaveNote}
      />

      {/* Note View Modal */}
      <NoteViewModal
        isOpen={Boolean(viewingNote)}
        note={viewingNote}
        onClose={() => setViewingNote(null)}
        onEdit={openEditModal}
        onDelete={(note) => setDeletingNote(note)}
      />

      {/* Note Deletion Confirmation Modal */}
      <DeleteNoteModal
        isOpen={Boolean(deletingNote)}
        note={deletingNote}
        onClose={() => setDeletingNote(null)}
        onConfirm={handleDeleteNote}
      />

      {/* PDF Upload Modal */}
      <UploadPdfModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onSuccess={handleUploadSuccess}
      />

      {/* Citation Detail Modal */}
      <CitationModal
        isOpen={Boolean(activeCitation)}
        citation={activeCitation}
        onClose={() => setActiveCitation(null)}
        onViewSource={handleViewSourceById}
      />
    </div>
  )
}
