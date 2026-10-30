import React, { useState, useRef, useEffect } from 'react'
import {
  Sparkles,
  Send,
  BookOpen,
  AlertCircle,
  CheckCircle2,
  RotateCcw,
  Loader2,
  FileText,
} from 'lucide-react'
import { ChatMessage, Citation } from '../types/chat'
import { notesApi, ApiError } from '../lib/api'

interface ChatPanelProps {
  onCitationClick: (citation: Citation) => void
  onViewSource?: (sourceId: string) => void
  className?: string
}

const SAMPLE_PROMPTS = [
  'What are the key points in my notes?',
  'Summarize the uploaded documents.',
  'How is data persisted in the architecture?',
]

export const ChatPanel: React.FC<ChatPanelProps> = ({
  onCitationClick,
  className = '',
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastQuestion, setLastQuestion] = useState<string | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, isLoading, error])

  const handleSend = async (questionToSend?: string) => {
    const q = (questionToSend || input).trim()
    if (!q || isLoading) return

    setInput('')
    setError(null)
    setLastQuestion(q)

    const userMessage: ChatMessage = {
      id: Math.random().toString(36).substring(2, 9),
      role: 'user',
      content: q,
      timestamp: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, userMessage])
    setIsLoading(true)

    try {
      const response = await notesApi.chat({ question: q })
      const assistantMessage: ChatMessage = {
        id: Math.random().toString(36).substring(2, 9),
        role: 'assistant',
        content: response.answer,
        citations: response.citations,
        grounded: response.grounded,
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, assistantMessage])
    } catch (err: any) {
      const errorMsg =
        err instanceof ApiError
          ? err.detail
          : err?.detail || err?.message || 'Failed to generate answer. Please try again.'
      setError(errorMsg)
    } finally {
      setIsLoading(false)
      setTimeout(() => textareaRef.current?.focus(), 100)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleClear = () => {
    setMessages([])
    setError(null)
    setLastQuestion(null)
  }

  const handleRetry = () => {
    if (lastQuestion) {
      handleSend(lastQuestion)
    }
  }

  return (
    <section
      className={`flex flex-col bg-[#0E1118] border-l border-[#1F2633] ${className}`}
      aria-label="Grounded Q&A Chat Panel"
    >
      {/* Header */}
      <div className="flex h-16 items-center justify-between border-b border-[#1F2633] px-4 md:px-5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-500/10 text-[#A78BFA] border border-purple-500/20">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <span className="text-xs font-semibold tracking-tight text-white block">Grounded Q&A</span>
            <span className="text-[10px] text-[#64748B] font-mono">nemotron-3.5-lightning</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {messages.length > 0 && (
            <button
              onClick={handleClear}
              className="flex items-center gap-1 rounded-lg border border-[#1F2633] bg-[#171C26] px-2.5 py-1 text-[11px] text-[#94A3B8] hover:text-white hover:bg-[#1E2433] transition-colors"
              title="Clear conversation"
              aria-label="Clear conversation"
            >
              <RotateCcw className="h-3 w-3" />
              <span>Reset</span>
            </button>
          )}
          <span className="rounded-full bg-[#171C26] px-2.5 py-0.5 text-[10px] font-mono text-[#94A3B8] border border-[#1F2633]">
            RAG Verified
          </span>
        </div>
      </div>

      {/* Message Feed */}
      <div className="flex-1 overflow-y-auto p-4 md:p-5 space-y-4">
        {messages.length === 0 && !isLoading && !error && (
          <div className="rounded-2xl border border-dashed border-[#1F2633] bg-[#11151D]/40 p-6 text-center space-y-3 my-auto">
            <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-[#171C26] text-[#8B5CF6] border border-[#1F2633]">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Ask your Second Brain</h3>
              <p className="mt-1 text-xs text-[#94A3B8] max-w-xs mx-auto leading-relaxed">
                Answers are generated strictly from your saved notes and PDFs, complete with clickable source citations.
              </p>
            </div>
            <div className="pt-2 flex flex-col gap-1.5 text-left">
              <span className="text-[10px] font-semibold text-[#64748B] uppercase tracking-wider">
                Try asking
              </span>
              {SAMPLE_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => handleSend(prompt)}
                  className="rounded-lg border border-[#1F2633] bg-[#171C26]/70 px-3 py-2 text-xs text-[#E2E8F0] hover:border-[#8B5CF6]/50 hover:bg-[#1E2433] hover:text-white transition-colors text-left"
                >
                  "{prompt}"
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {msg.role === 'user' ? (
              <div
                className="max-w-[85%] rounded-2xl rounded-tr-xs bg-[#8B5CF6] px-4 py-2.5 text-xs text-white shadow-md shadow-purple-950/30 whitespace-pre-wrap leading-relaxed"
                data-testid="user-message"
              >
                {msg.content}
              </div>
            ) : (
              <div
                className="max-w-[92%] rounded-2xl rounded-tl-xs border border-[#1F2633] bg-[#11151D] p-4 text-xs text-[#E2E8F0] space-y-3 shadow-sm"
                data-testid="assistant-message"
              >
                {/* Assistant Bubble Header: Status & Grounding Badge */}
                <div className="flex items-center justify-between pb-2 border-b border-[#1F2633]/60 gap-2">
                  <div className="flex items-center gap-1.5 font-medium text-white text-[11px]">
                    <Sparkles className="h-3.5 w-3.5 text-[#8B5CF6]" />
                    <span>AI Assistant</span>
                  </div>
                  {msg.grounded ? (
                    <span
                      data-testid="grounded-badge"
                      className="inline-flex items-center gap-1 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 text-[10px] font-medium"
                    >
                      <CheckCircle2 className="h-3 w-3" />
                      <span>Grounded in Sources</span>
                    </span>
                  ) : (
                    <span
                      data-testid="ungrounded-badge"
                      className="inline-flex items-center gap-1 rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2 py-0.5 text-[10px] font-medium"
                    >
                      <AlertCircle className="h-3 w-3" />
                      <span>No Sources Found</span>
                    </span>
                  )}
                </div>

                {/* Answer Body */}
                <div className="leading-relaxed whitespace-pre-wrap text-[#F3F4F6] select-text">
                  {msg.content}
                </div>

                {/* Clickable Source Citations */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="pt-2 border-t border-[#1F2633]/60 space-y-2">
                    <div className="text-[10px] font-semibold text-[#64748B] uppercase tracking-wider flex items-center gap-1">
                      <BookOpen className="h-3 w-3 text-[#8B5CF6]" />
                      <span>Sources Cited ({msg.citations.length})</span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {msg.citations.map((citation) => {
                        const pageLabel =
                          citation.page_number !== null && citation.page_number !== undefined
                            ? `Page ${citation.page_number}`
                            : 'Note'
                        return (
                          <button
                            key={citation.label}
                            onClick={() => onCitationClick(citation)}
                            className="group flex items-center gap-1.5 rounded-lg bg-[#171C26] hover:bg-[#1E2433] hover:border-[#8B5CF6]/60 border border-[#262E3D] px-2.5 py-1.5 text-[11px] text-[#A78BFA] transition-all cursor-pointer shadow-xs"
                            title={`View citation ${citation.label} (${citation.title})`}
                            aria-label={`View citation ${citation.label}: ${citation.title} ${pageLabel}`}
                          >
                            <span className="font-mono font-bold text-white text-[10px] bg-purple-500/20 px-1 py-0.5 rounded">
                              {citation.label}
                            </span>
                            <span className="truncate max-w-[170px] text-[#E2E8F0] group-hover:text-white font-medium">
                              {citation.title}
                            </span>
                            <span className="text-[10px] text-[#64748B] font-mono bg-[#0E1118] px-1 py-0.5 rounded border border-[#1F2633]">
                              {pageLabel}
                            </span>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {/* Loading Indicator */}
        {isLoading && (
          <div
            data-testid="chat-loading"
            className="flex justify-start animate-in fade-in duration-200"
          >
            <div className="max-w-[85%] rounded-2xl rounded-tl-xs border border-purple-500/30 bg-[#11151D] p-4 text-xs text-[#A78BFA] space-y-2 shadow-md shadow-purple-950/20">
              <div className="flex items-center gap-2 font-medium">
                <Loader2 className="h-4 w-4 animate-spin text-[#8B5CF6]" />
                <span>Searching sources & generating grounded response...</span>
              </div>
              <div className="space-y-1.5 pt-1">
                <div className="h-2 w-48 rounded-full bg-purple-500/20 animate-pulse" />
                <div className="h-2 w-36 rounded-full bg-purple-500/10 animate-pulse" />
              </div>
            </div>
          </div>
        )}

        {/* Provider Error Banner */}
        {error && (
          <div
            role="alert"
            data-testid="chat-error-banner"
            className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3.5 text-xs text-rose-300 space-y-2 animate-in fade-in"
          >
            <div className="flex items-start gap-2">
              <AlertCircle className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />
              <div className="flex-1">
                <span className="font-semibold block text-white text-xs">AI Chat Error</span>
                <span className="text-rose-200/90 leading-relaxed block mt-0.5">{error}</span>
              </div>
            </div>
            {lastQuestion && (
              <div className="flex justify-end pt-1">
                <button
                  onClick={handleRetry}
                  className="rounded-lg bg-rose-600/30 hover:bg-rose-600/50 border border-rose-500/40 px-3 py-1 text-xs text-white font-medium transition-colors"
                >
                  Retry Question
                </button>
              </div>
            )}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Composer Input Area */}
      <div className="border-t border-[#1F2633] bg-[#11151D] p-3 md:p-4">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            handleSend()
          }}
          className="relative"
        >
          <textarea
            ref={textareaRef}
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            placeholder="Ask a question about your library... (Enter to send)"
            aria-label="Ask a question"
            className="w-full resize-none rounded-xl border border-[#1F2633] bg-[#171C26] p-3 pr-11 text-xs text-white placeholder-[#64748B] focus:border-[#8B5CF6] focus:outline-hidden focus:ring-1 focus:ring-[#8B5CF6]/50 disabled:opacity-50 transition-all"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            aria-label="Send question"
            className="absolute right-2.5 bottom-3 flex h-7 w-7 items-center justify-center rounded-lg bg-[#8B5CF6] hover:bg-[#7C3AED] text-white disabled:opacity-40 disabled:hover:bg-[#8B5CF6] transition-colors shadow-xs"
          >
            {isLoading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Send className="h-3.5 w-3.5" />
            )}
          </button>
        </form>
        <div className="mt-2 flex items-center justify-between text-[10px] text-[#64748B]">
          <span className="flex items-center gap-1">
            <FileText className="h-3 w-3" />
            <span>Grounded in indexed library chunks</span>
          </span>
          <span className="font-mono">Shift+Enter for newline</span>
        </div>
      </div>
    </section>
  )
}
