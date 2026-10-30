import { Note, NoteCreateInput, NoteListResponse, NoteUpdateInput } from '../types/note'
import { ChatRequest, ChatResponse, Citation } from '../types/chat'

export type { Citation, ChatRequest, ChatResponse }

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(`API Error ${status}: ${detail}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {})
  if (!headers.has('Content-Type') && options.body && typeof options.body === 'string') {
    headers.set('Content-Type', 'application/json')
  }

  let response: Response
  try {
    response = await fetch(endpoint, {
      ...options,
      headers,
    })
  } catch (err: any) {
    throw new ApiError(
      0,
      `Network error: Unable to reach backend server. Ensure the backend is running on http://127.0.0.1:8000.`
    )
  }

  if (response.status === 204) {
    return null as unknown as T
  }

  let data: any
  const contentType = response.headers.get('content-type')
  if (contentType && contentType.includes('application/json')) {
    try {
      data = await response.json()
    } catch {
      data = null
    }
  } else {
    data = await response.text()
  }

  if (!response.ok) {
    const detail =
      data && typeof data === 'object' && 'detail' in data
        ? typeof data.detail === 'string'
          ? data.detail
          : typeof data.detail === 'object' && data.detail && 'detail' in data.detail
          ? data.detail.detail
          : JSON.stringify(data.detail)
        : typeof data === 'string' && data.trim()
        ? data.trim()
        : response.statusText || `Request failed with status ${response.status}`
    throw new ApiError(response.status, detail)
  }

  return data as T
}

export const notesApi = {
  async listNotes(params: {
    tag?: string
    q?: string
    limit?: number
    offset?: number
  } = {}): Promise<NoteListResponse> {
    const searchParams = new URLSearchParams()
    if (params.tag) searchParams.set('tag', params.tag)
    if (params.q) searchParams.set('q', params.q)
    if (params.limit !== undefined) searchParams.set('limit', params.limit.toString())
    if (params.offset !== undefined) searchParams.set('offset', params.offset.toString())

    const query = searchParams.toString()
    const url = `/api/v1/notes${query ? `?${query}` : ''}`
    return request<NoteListResponse>(url)
  },

  async getNote(id: string): Promise<Note> {
    return request<Note>(`/api/v1/notes/${id}`)
  },

  async createNote(data: NoteCreateInput): Promise<Note> {
    return request<Note>('/api/v1/notes', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async updateNote(id: string, data: NoteUpdateInput): Promise<Note> {
    return request<Note>(`/api/v1/notes/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  },

  async deleteNote(id: string): Promise<void> {
    return request<void>(`/api/v1/notes/${id}`, {
      method: 'DELETE',
    })
  },

  async uploadDocument(file: File): Promise<Note> {
    const formData = new FormData()
    formData.append('file', file)
    return request<Note>('/api/v1/documents', {
      method: 'POST',
      body: formData,
    })
  },

  async listSources(params: {
    kind?: string
    tag?: string
    q?: string
    limit?: number
    offset?: number
  } = {}): Promise<NoteListResponse> {
    const searchParams = new URLSearchParams()
    if (params.kind) searchParams.set('kind', params.kind)
    if (params.tag) searchParams.set('tag', params.tag)
    if (params.q) searchParams.set('q', params.q)
    if (params.limit !== undefined) searchParams.set('limit', params.limit.toString())
    if (params.offset !== undefined) searchParams.set('offset', params.offset.toString())

    const query = searchParams.toString()
    const url = `/api/v1/sources${query ? `?${query}` : ''}`
    return request<NoteListResponse>(url)
  },

  async deleteSource(id: string): Promise<void> {
    return request<void>(`/api/v1/sources/${id}`, {
      method: 'DELETE',
    })
  },

  async chat(data: ChatRequest): Promise<ChatResponse> {
    return request<ChatResponse>('/api/v1/chat', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async checkHealth(): Promise<{ status: string }> {
    return request<{ status: string }>('/health')
  },

  async checkReadiness(): Promise<{ status: string; database: string }> {
    return request<{ status: string; database: string }>('/api/v1/health/ready')
  },
}
