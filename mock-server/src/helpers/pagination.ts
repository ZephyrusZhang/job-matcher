export function paginate<T>(items: T[], page: number, pageSize: number) {
  const total = items.length;
  const total_pages = Math.ceil(total / pageSize);
  const start = (page - 1) * pageSize;
  const data = items.slice(start, start + pageSize);

  return {
    data,
    pagination: {
      page,
      page_size: pageSize,
      total,
      total_pages,
    },
  };
}
