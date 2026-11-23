export function formatDate(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? "Unknown"
    : new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(parsed);
}
