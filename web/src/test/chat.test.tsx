import { describe, it, expect, vi, beforeEach } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import App from '../App'
import { ChatPanel } from '../components/ChatPanel'
import { CitationModal } from '../components/CitationModal'
import { notesApi, ApiError } from '../lib/api'
import { Citation, ChatResponse } from '../types/chat'

// Mock the API layer
vi.mock('../lib/api', () => ({
  notesApi: {
    listNotes: vi.fn().mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 }),
    getNote: vi.fn(),
    createNote: vi.fn(),
    updateNote: vi.fn(),
    deleteNote: vi.fn(),
    uploadDocument: vi.fn(),
    chat: vi.fn(),
    checkHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
    checkReadiness: vi.fn().mockResolvedValue({ status: 'ready', database: 'connected' }),
  },
  ApiError: class ApiError extends Error {
    status: number
    detail: string
    constructor(status: number, detail: string) {
      super(`API Error ${status}: ${detail}`)
      this.name = 'ApiError'
      this.status = status
      this.detail = detail
    }
  },
}))

const mockCitation: Citation = {
  label: '[S1]',
  chunk_id: 'chunk-uuid-1',
  source_id: 'source-uuid-1',
  title: 'Attention Is All You Need.pdf',
  page_number: 3,
  excerpt: 'The self-attention mechanism connects all positions with constant path length.',
}

const mockChatResponse: ChatResponse = {
  question: 'How does self-attention work?',
  answer: 'Self-attention connects all positions in parallel [S1].',
  citations: [mockCitation],
  grounded: true,
  model_id: 'nvidia/nemotron-3.5-lightning:free',
  retrieved_chunks_count: 1,
}

describe('ChatPanel Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders empty onboarding state with sample prompts', () => {
    const handleCitationClick = vi.fn()
    render(<ChatPanel onCitationClick={handleCitationClick} />)

    expect(screen.getByText(/ask your second brain/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/ask a question about your library/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /send question/i })).toBeDisabled()
  })

  it('sends question, displays loading state, and renders assistant answer with citations', async () => {
    const handleCitationClick = vi.fn()
    vi.mocked(notesApi.chat).mockResolvedValueOnce(mockChatResponse)

    render(<ChatPanel onCitationClick={handleCitationClick} />)

    const textarea = screen.getByPlaceholderText(/ask a question about your library/i)
    fireEvent.change(textarea, { target: { value: 'How does self-attention work?' } })

    const sendBtn = screen.getByRole('button', { name: /send question/i })
    expect(sendBtn).not.toBeDisabled()
    fireEvent.click(sendBtn)

    // User message should appear immediately
    expect(screen.getByTestId('user-message')).toHaveTextContent('How does self-attention work?')

    // Loading indicator should appear while request is pending
    expect(screen.getByTestId('chat-loading')).toBeInTheDocument()

    // Assistant answer should appear on resolution
    expect(await screen.findByTestId('assistant-message')).toBeInTheDocument()
    expect(screen.getByText(/self-attention connects all positions in parallel/i)).toBeInTheDocument()
    expect(screen.getByTestId('grounded-badge')).toHaveTextContent(/grounded in sources/i)

    // Citations list should be rendered
    const citationBtn = screen.getByRole('button', {
      name: /view citation \[s1\]: attention is all you need\.pdf page 3/i,
    })
    expect(citationBtn).toBeInTheDocument()

    // Clicking citation calls onCitationClick with the verified metadata
    fireEvent.click(citationBtn)
    expect(handleCitationClick).toHaveBeenCalledWith(mockCitation)
  })

  it('handles Enter key press to submit without Shift key', async () => {
    const handleCitationClick = vi.fn()
    vi.mocked(notesApi.chat).mockResolvedValueOnce(mockChatResponse)

    render(<ChatPanel onCitationClick={handleCitationClick} />)

    const textarea = screen.getByPlaceholderText(/ask a question about your library/i)
    fireEvent.change(textarea, { target: { value: 'Keyboard submit question' } })
    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter', shiftKey: false })

    await waitFor(() => {
      expect(notesApi.chat).toHaveBeenCalledWith({ question: 'Keyboard submit question' })
    })
  })

  it('displays provider error banner and allows retry', async () => {
    const handleCitationClick = vi.fn()
    vi.mocked(notesApi.chat).mockRejectedValueOnce(
      new ApiError(503, 'AI chat is not configured. Set OPENROUTER_API_KEY in the backend environment.')
    )

    render(<ChatPanel onCitationClick={handleCitationClick} />)

    const textarea = screen.getByPlaceholderText(/ask a question about your library/i)
    fireEvent.change(textarea, { target: { value: 'Test error question' } })
    fireEvent.click(screen.getByRole('button', { name: /send question/i }))

    // Error banner appears with the provider error message
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(
      screen.getByText(/AI chat is not configured. Set OPENROUTER_API_KEY in the backend environment./i)
    ).toBeInTheDocument()

    // Retry button is available
    const retryBtn = screen.getByRole('button', { name: /retry question/i })
    expect(retryBtn).toBeInTheDocument()

    // Mock success on retry
    vi.mocked(notesApi.chat).mockResolvedValueOnce(mockChatResponse)
    fireEvent.click(retryBtn)

    expect(await screen.findByTestId('assistant-message')).toBeInTheDocument()
  })

  it('displays no-sources badge when answer is not grounded', async () => {
    const handleCitationClick = vi.fn()
    vi.mocked(notesApi.chat).mockResolvedValueOnce({
      question: 'Unknown topic?',
      answer: "I couldn't find this in your sources. Try adding relevant notes or PDFs to your library.",
      citations: [],
      grounded: false,
      model_id: 'nvidia/nemotron-3.5-lightning:free',
      retrieved_chunks_count: 0,
    })

    render(<ChatPanel onCitationClick={handleCitationClick} />)

    const textarea = screen.getByPlaceholderText(/ask a question about your library/i)
    fireEvent.change(textarea, { target: { value: 'Unknown topic?' } })
    fireEvent.click(screen.getByRole('button', { name: /send question/i }))

    expect(await screen.findByTestId('assistant-message')).toBeInTheDocument()
    expect(screen.getByTestId('ungrounded-badge')).toHaveTextContent(/no sources found/i)
  })
})

describe('CitationModal Component', () => {
  it('renders citation details including document title, page number, and quoted excerpt', () => {
    const handleClose = vi.fn()
    const handleViewSource = vi.fn()

    render(
      <CitationModal
        isOpen={true}
        citation={mockCitation}
        onClose={handleClose}
        onViewSource={handleViewSource}
      />
    )

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('[S1]')).toBeInTheDocument()
    expect(screen.getByText('Attention Is All You Need.pdf')).toBeInTheDocument()
    expect(screen.getByText('PDF Page 3')).toBeInTheDocument()
    expect(
      screen.getByText(/the self-attention mechanism connects all positions with constant path length/i)
    ).toBeInTheDocument()
    expect(screen.getByText(/chunk:chunk-uu/i)).toBeInTheDocument()

    // View source button
    const viewSourceBtn = screen.getByRole('button', { name: /view full source/i })
    fireEvent.click(viewSourceBtn)
    expect(handleViewSource).toHaveBeenCalledWith('source-uuid-1')
    expect(handleClose).toHaveBeenCalled()
  })

  it('closes on Escape key press or Done button click', () => {
    const handleClose = vi.fn()

    render(
      <CitationModal
        isOpen={true}
        citation={mockCitation}
        onClose={handleClose}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: /done/i }))
    expect(handleClose).toHaveBeenCalledTimes(1)

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(handleClose).toHaveBeenCalledTimes(2)
  })
})

describe('Integrated App Chat Flow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(notesApi.listNotes).mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 })
  })

  it('allows asking a question and clicking citation opens the citation modal in App', async () => {
    vi.mocked(notesApi.chat).mockResolvedValueOnce(mockChatResponse)

    render(<App />)

    // Chat panel is visible in desktop view
    const textarea = screen.getByPlaceholderText(/ask a question about your library/i)
    fireEvent.change(textarea, { target: { value: 'How does self-attention work?' } })
    fireEvent.click(screen.getByRole('button', { name: /send question/i }))

    // Wait for response and citation to appear
    expect(await screen.findByTestId('assistant-message')).toBeInTheDocument()
    const citationBtn = screen.getByRole('button', {
      name: /view citation \[s1\]: attention is all you need\.pdf page 3/i,
    })
    expect(citationBtn).toBeInTheDocument()

    // Click the citation
    fireEvent.click(citationBtn)

    // Citation modal should open
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Attention Is All You Need.pdf' })).toBeInTheDocument()
    expect(screen.getByText('PDF Page 3')).toBeInTheDocument()
    expect(
      screen.getByText(/the self-attention mechanism connects all positions with constant path length/i)
    ).toBeInTheDocument()
  })
})

