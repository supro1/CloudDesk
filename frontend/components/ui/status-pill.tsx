const toneByStatus: Record<string, string> = {
  resolved: "pill-green",
  closed: "pill-green",
  approved: "pill-green",
  active: "pill-green",
  waiting_on_approval: "pill-amber",
  pending: "pill-amber",
  escalated: "pill-red",
  rejected: "pill-red",
  critical: "pill-red",
  high: "pill-amber",
  medium: "pill-blue",
};

export function StatusPill({ value }: { value: string | null }) {
  const label = value ? value.replaceAll("_", " ") : "Unclassified";
  const tone = value ? toneByStatus[value] ?? "" : "";
  return <span className={`pill ${tone}`}>{label}</span>;
}
