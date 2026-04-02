import { ApiResponse, ApiError } from '@/types/api'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:3001'

async function handleResponse<T>(res: Response): Promise<ApiResponse<T>> {
  const body = await res.json()

  if (!res.ok) {
    throw new ApiError(
      body.error?.code ?? 'UNKNOWN_ERROR',
      body.error?.message ?? res.statusText,
      res.status,
    )
  }

  return body as ApiResponse<T>
}

export async function apiGet<T>(
  path: string,
  params?: Record<string, string | undefined>,
): Promise<ApiResponse<T>> {
  const url = new URL(`${API_BASE}${path}`)
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        url.searchParams.set(key, value)
      }
    })
  }

  const res = await fetch(url.toString(), {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  })

  return handleResponse<T>(res)
}

export async function apiPost<T>(
  path: string,
  body?: unknown,
): Promise<ApiResponse<T>> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  return handleResponse<T>(res)
}

export async function apiPatch<T>(
  path: string,
  body?: unknown,
): Promise<ApiResponse<T>> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  return handleResponse<T>(res)
}

export async function apiDelete<T>(
  path: string,
): Promise<ApiResponse<T>> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
  })

  return handleResponse<T>(res)
}
