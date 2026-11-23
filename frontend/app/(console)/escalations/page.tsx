"use client";

import { useCallback, useState } from "react";
import { EmptyState } from "@/components/ui/empty-state";
import { Notice } from "@/components/ui/notice";
import { PageHeading } from "@/components/ui/page-heading";
import { PaginationControls } from "@/components/ui/pagination-controls";
import { StatusPill } from "@/components/ui/status-pill";
import { listEscalations } from "@/lib/api";
import { useApiData } from "@/lib/use-api-data";
import { formatDate } from "@/lib/format";

const PAGE_SIZE = 20;

export default function EscalationsPage() {
  const [offset, setOffset] = useState(0);
  const load = useCallback(() => listEscalations({ limit: PAGE_SIZE, offset }), [offset]);
  const { data, error, loading, retry } = useApiData(load);

  return (
    <>
      <PageHeading eyebrow="Specialist review" title="Escalations" description="Review cases routed to specialist support teams." />
      {error && <Notice error={error} onRetry={retry} />}
      <section className="panel" aria-label="Escalation list">
        {loading && !data ? <div className="loading-state">Loading escalations…</div> : !data?.items.length ? (
          <EmptyState title="No escalations yet" message="Cases routed for specialist review will appear here." />
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Team</th><th>Reason</th><th>Ticket</th><th>Status</th><th>Created</th></tr></thead>
                <tbody>
                  {data.items.map((escalation) => (
                    <tr key={escalation.id}>
                      <td className="primary-cell">{escalation.team.replaceAll("_", " ")}</td>
                      <td>{escalation.reason}</td>
                      <td className="mono muted">{escalation.ticket_id.slice(0, 8)}…</td>
                      <td><StatusPill value={escalation.status} /></td>
                      <td className="mono">{formatDate(escalation.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <PaginationControls total={data.total} limit={data.limit} offset={data.offset} onChange={setOffset} />
          </>
        )}
      </section>
    </>
  );
}
