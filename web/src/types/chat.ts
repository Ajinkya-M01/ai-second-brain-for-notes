export interface Citation {
  label: string
  chunk_id: string
  source_id: string
  title: string
  page_number?: number | null
  excerpt: string
}

export interface ChatRequest {
  question: string
  source_ids?: string[]
  limit?: number
  min_similarity?: number
  conversation_id?: string
}

export interface ChatResponse {
  question: string
  answer: string
  citations: Citation[]
  grounded: boolean
  model_id?: string
  retrieved_chunks_count: number
  conversation_id?: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  grounded?: boolean
  timestamp: string
  error?: string | null
}

