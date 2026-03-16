function flattenSearchValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) {
    return value.map((item) => flattenSearchValue(item)).filter(Boolean).join(" ");
  }
  if (typeof value === "object") {
    return Object.values(value as Record<string, unknown>)
      .map((item) => flattenSearchValue(item))
      .filter(Boolean)
      .join(" ");
  }
  return String(value);
}

export function matchesTableSearch(query: string, values: unknown[]) {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return true;

  return values.some((value) => flattenSearchValue(value).toLowerCase().includes(normalizedQuery));
}
