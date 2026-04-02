export interface ApiResponse<T> {
  success: boolean
  data: T
  error: { code: string; message: string } | null
  pagination: PaginationMeta | null
}

export interface PaginationMeta {
  page: number
  page_size: number
  total: number
  total_pages: number
}

export class ApiError extends Error {
  code: string
  status: number
  constructor(code: string, message: string, status: number) {
    super(message)
    this.code = code
    this.status = status
  }
}
