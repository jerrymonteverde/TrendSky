export const MAX_QUERY_LENGTH = 120;
export function normalizeQuery(query: string): string {
  return query.trim().replace(/\s+/g, " ").slice(0, MAX_QUERY_LENGTH);
}
export function exploreUrl(query: string): string {
  const value = normalizeQuery(query);
  return value ? `/explore?${new URLSearchParams({ q: value })}` : "/explore";
}
