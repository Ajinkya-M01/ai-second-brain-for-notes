import { describe, it, expect, vi, beforeEach } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import App from '../App'
import { NoteModal } from '../components/NoteModal'
import { DeleteNoteModal } from '../components/DeleteNoteModal'
import { NoteViewModal } from '../components/NoteViewModal'
import { UploadPdfModal } from '../components/UploadPdfModal'
import { notesApi } from '../lib/api'
import { Note } from '../types/note'

// Mock the API layer
vi.mock('../lib/api', () => ({
  notesApi: {
    listNotes: vi.fn(),
    createNote: vi.fn(),
    updateNote: vi.fn(),
    deleteNote: vi.fn(),
    uploadDocument: vi.fn(),
    checkHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
    checkReadiness: vi.fn().mockResolvedValue({ status: 'ready', database: 'connected' }),
  },
}))

const mockNote: Note = {
  id: 'test-uuid-1',
  kind: 'note',
  title: 'FastAPI Architecture',
  content: 'Modular structure with SQLAlchemy and Pydantic.',
  original_filename: null,
  mime_type: 'text/plain',
  size_bytes: 47,
  content_sha256: 'abc123sha256',
  status: 'pending',
  error_message: null,
  tags: ['fastapi', 'backend'],
  created_at: '2026-10-14T10:00:00Z',
  updated_at: '2026-10-14T10:30:00Z',
}

describe('NoteModal Component', () => {
  it('validates that title is required', async () => {
    const handleSave = vi.fn()
    const handleClose = vi.fn()

    render(
      <NoteModal
        isOpen={true}
        onClose={handleClose}
        onSave={handleSave}
      />
    )

    // Attempt submit with empty title
    const submitBtn = screen.getByRole('button', { name: /create note/i })
    fireEvent.click(submitBtn)

    expect(await screen.findByText('Please enter a note title.')).toBeInTheDocument()
    expect(handleSave).not.toHaveBeenCalled()
  })

  it('validates that content is required when title is provided', async () => {
    const handleSave = vi.fn()
    const handleClose = vi.fn()

    render(
      <NoteModal
        isOpen={true}
        onClose={handleClose}
        onSave={handleSave}
      />
    )

    fireEvent.change(screen.getByLabelText(/title/i), { target: { value: 'Valid Title' } })
    fireEvent.click(screen.getByRole('button', { name: /create note/i }))

    expect(await screen.findByText('Note content cannot be empty.')).toBeInTheDocument()
    expect(handleSave).not.toHaveBeenCalled()
  })

  it('submits note with title, content, and tags', async () => {
    const handleSave = vi.fn().mockResolvedValue(undefined)
    const handleClose = vi.fn()

    render(
      <NoteModal
        isOpen={true}
        onClose={handleClose}
        onSave={handleSave}
      />
    )

    fireEvent.change(screen.getByLabelText(/title/i), { target: { value: 'Distributed Systems' } })
    fireEvent.change(screen.getByLabelText(/content/i), { target: { value: 'Notes on Paxos and Raft.' } })

    const tagInput = screen.getByPlaceholderText(/type tag and press enter/i)
    fireEvent.change(tagInput, { target: { value: 'distributed' } })
    fireEvent.keyDown(tagInput, { key: 'Enter', code: 'Enter' })

    fireEvent.click(screen.getByRole('button', { name: /create note/i }))

    await waitFor(() => {
      expect(handleSave).toHaveBeenCalledWith({
        title: 'Distributed Systems',
        content: 'Notes on Paxos and Raft.',
        tags: ['distributed'],
      })
      expect(handleClose).toHaveBeenCalled()
    })
  })

  it('pre-populates existing data in edit mode', () => {
    render(
      <NoteModal
        isOpen={true}
        note={mockNote}
        onClose={vi.fn()}
        onSave={vi.fn()}
      />
    )

    expect(screen.getByDisplayValue('FastAPI Architecture')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Modular structure with SQLAlchemy and Pydantic.')).toBeInTheDocument()
    expect(screen.getByText('#fastapi')).toBeInTheDocument()
    expect(screen.getByText('#backend')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save changes/i })).toBeInTheDocument()
  })
})

describe('DeleteNoteModal Component', () => {
  it('displays note title and calls onConfirm on deletion', async () => {
    const handleConfirm = vi.fn().mockResolvedValue(undefined)
    const handleClose = vi.fn()

    render(
      <DeleteNoteModal
        isOpen={true}
        note={mockNote}
        onClose={handleClose}
        onConfirm={handleConfirm}
      />
    )

    expect(screen.getByText(/FastAPI Architecture/i)).toBeInTheDocument()
    const deleteBtn = screen.getByRole('button', { name: /delete note/i })
    fireEvent.click(deleteBtn)

    await waitFor(() => {
      expect(handleConfirm).toHaveBeenCalledWith('test-uuid-1')
      expect(handleClose).toHaveBeenCalled()
    })
  })
})

describe('NoteViewModal Component', () => {
  it('renders note content and calls onEdit and onDelete handlers', () => {
    const handleEdit = vi.fn()
    const handleDelete = vi.fn()
    const handleClose = vi.fn()

    render(
      <NoteViewModal
        isOpen={true}
        note={mockNote}
        onClose={handleClose}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />
    )

    expect(screen.getByText('FastAPI Architecture')).toBeInTheDocument()
    expect(screen.getByText(/Modular structure with SQLAlchemy/)).toBeInTheDocument()

    // Test edit button
    const editBtn = screen.getByRole('button', { name: /edit/i })
    fireEvent.click(editBtn)
    expect(handleEdit).toHaveBeenCalledWith(mockNote)

    // Test delete button
    const deleteBtn = screen.getByRole('button', { name: /delete/i })
    fireEvent.click(deleteBtn)
    expect(handleDelete).toHaveBeenCalledWith(mockNote)
  })
})

describe('App Library Flow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders empty state when notes list is empty', async () => {
    vi.mocked(notesApi.listNotes).mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    })

    render(<App />)

    expect(await screen.findByTestId('notes-empty-state')).toBeInTheDocument()
    expect(screen.getByText('Your library is empty')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create your first note/i })).toBeInTheDocument()
  })

  it('renders note cards when notes are returned', async () => {
    vi.mocked(notesApi.listNotes).mockResolvedValueOnce({
      items: [mockNote],
      total: 1,
      limit: 50,
      offset: 0,
    })

    render(<App />)

    expect(await screen.findByText('FastAPI Architecture')).toBeInTheDocument()
    expect(screen.getByText(/Modular structure with SQLAlchemy and Pydantic/)).toBeInTheDocument()
    expect(screen.getAllByText('#fastapi').length).toBeGreaterThanOrEqual(1)
  })

  it('renders error state and retry button when API fails', async () => {
    vi.mocked(notesApi.listNotes).mockRejectedValueOnce(new Error('Connection refused'))

    render(<App />)

    expect(await screen.findByText('Failed to load notes')).toBeInTheDocument()
    expect(screen.getByText('Connection refused')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})

const mockPdfSource: Note = {
  id: 'pdf-uuid-1',
  kind: 'pdf',
  title: 'Attention Is All You Need',
  content: '--- Page 1 ---\nAttention Is All You Need Paper',
  original_filename: 'attention_is_all_you_need.pdf',
  mime_type: 'application/pdf',
  size_bytes: 432,
  content_sha256: 'deadbeef123456',
  status: 'indexed',
  error_message: null,
  tags: [],
  created_at: '2026-10-14T12:00:00Z',
  updated_at: '2026-10-14T12:00:00Z',
}

describe('UploadPdfModal Component', () => {
  it('calls uploadDocument and invokes onSuccess with the returned source on success', async () => {
    const handleSuccess = vi.fn()
    const handleClose = vi.fn()
    vi.mocked(notesApi.uploadDocument).mockResolvedValueOnce(mockPdfSource)

    render(
      <UploadPdfModal
        isOpen={true}
        onClose={handleClose}
        onSuccess={handleSuccess}
      />
    )

    // The upload area and submit button should be rendered
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /upload & extract/i })).toBeInTheDocument()

    // Simulate selecting a PDF file via the hidden input
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['%PDF-1.4 sample content'], 'attention_is_all_you_need.pdf', {
      type: 'application/pdf',
    })
    fireEvent.change(fileInput, { target: { files: [file] } })

    // The file should now be shown
    expect(await screen.findByText('attention_is_all_you_need.pdf')).toBeInTheDocument()

    // Submit the form
    fireEvent.click(screen.getByRole('button', { name: /upload & extract/i }))

    await waitFor(() => {
      expect(notesApi.uploadDocument).toHaveBeenCalledWith(file)
      expect(handleSuccess).toHaveBeenCalledWith(mockPdfSource)
      expect(handleClose).toHaveBeenCalled()
    })
  })

  it('shows an inline error banner when the API returns an error', async () => {
    const handleSuccess = vi.fn()
    const handleClose = vi.fn()
    // Simulate the ApiError shape that notesApi.uploadDocument throws
    const apiError = { detail: 'No extractable text found in PDF. This document appears to be scanned or contains only images. OCR is not supported in the MVP.' }
    vi.mocked(notesApi.uploadDocument).mockRejectedValueOnce(apiError)

    render(
      <UploadPdfModal
        isOpen={true}
        onClose={handleClose}
        onSuccess={handleSuccess}
      />
    )

    // Simulate selecting a PDF file
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['%PDF-1.4 scanned'], 'scanned_doc.pdf', { type: 'application/pdf' })
    fireEvent.change(fileInput, { target: { files: [file] } })
    expect(await screen.findByText('scanned_doc.pdf')).toBeInTheDocument()

    // Submit
    fireEvent.click(screen.getByRole('button', { name: /upload & extract/i }))

    // Verify the error banner appears with the API message
    expect(
      await screen.findByText(/no extractable text found/i)
    ).toBeInTheDocument()

    // onSuccess must NOT have been called
    expect(handleSuccess).not.toHaveBeenCalled()
    // Modal should remain open (onClose not called)
    expect(handleClose).not.toHaveBeenCalled()
  })
})
