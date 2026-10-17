export interface Note {
  id: string
  kind: 'note' | 'pdf'
  title: string
  content?: string | null
  original_filename?: string | null
  mime_type: string
  size_bytes: number
  content_sha256: string
  status: 'pending' | 'indexed' | 'failed'
  error_message?: string | null
  tags: string[]
  created_at: string
  updated_at: string
}

export interface NoteCreateInput {
  title: string
  content: string
  tags?: string[]
}

export interface NoteUpdateInput {
  title?: string
  content?: string
  tags?: string[]
}

export interface NoteListResponse {
  items: Note[]
  total: number
  limit: number
  offset: number
}
