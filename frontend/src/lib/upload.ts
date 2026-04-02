import { ApiResponse, ApiError } from '@/types/api'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:3001'

export async function uploadFile<T>(
  path: string,
  file: File,
  fieldName: string = 'file',
): Promise<ApiResponse<T>> {
  const formData = new FormData()
  formData.append(fieldName, file)

  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    body: formData,
    // Do not set Content-Type — browser will set it with boundary
  })

  const body = await res.json()

  if (!res.ok) {
    throw new ApiError(
      body.error?.code ?? 'UPLOAD_ERROR',
      body.error?.message ?? res.statusText,
      res.status,
    )
  }

  return body as ApiResponse<T>
}
