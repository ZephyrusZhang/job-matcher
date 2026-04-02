export function ok<T>(data: T, pagination?: { page: number; page_size: number; total: number; total_pages: number }) {
  return {
    success: true as const,
    data,
    error: null,
    pagination: pagination ?? null,
  };
}

export function err(code: string, message: string) {
  return {
    success: false as const,
    data: null,
    error: { code, message },
    pagination: null,
  };
}
