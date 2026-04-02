export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface ChatHistory {
  report_id: string
  messages: ChatMessage[]
}

export interface ChatRequest {
  report_id: string
  message: string
}
