"use client";

import { useCallback, useState } from "react";
import { EmptyState } from "@/components/ui/empty-state";
import { Notice } from "@/components/ui/notice";
import { PageHeading } from "@/components/ui/page-heading";
import { PaginationControls } from "@/components/ui/pagination-controls";
import { StatusPill } from "@/components/ui/status-pill";
import { listTickets } from "@/lib/api";
import { useApiData } from "@/lib/use-api-data";
import { formatDate } from "@/lib/format";

const PAGE_SIZE = 20;

export default function TicketsPage() {
  const [offset, setOffset] = useState(0);
  const load = useCallback(() => listTickets({ limit: PAGE_SIZE, offset }), [offset]);
  const { data, error, loading, retry } = useApiData(load);

  return (
    <>
      <PageHeading eyebrow="Support" title="Tickets" description="Browse incoming and resolved customer requests." />
      {error && <Notice error={error} onRetry={retry} />}
      <section className="panel" aria-label="Ticket list">
        {loading && !data ? <div className="loading-state">Loading tickets…</div> : !data?.items.length ? (
          <EmptyState title="No tickets yet" message="Tickets will appear here when the support API has records." />
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Ticket</th><th>Status</th><th>Category</th><th>Severity</th><th>Channel</th><th>Created</th></tr></thead>
                <tbody>
                  {data.items.map((ticket) => (
                    <tr key={ticket.id}>
                      <td><div className="primary-cell">{ticket.ticket_number}</div><div className="secondary-cell">{ticket.subject}</div></td>
                      <td><StatusPill value={ticket.status} /></td>
                      <td><StatusPill value={ticket.category} /></td>
                      <td><StatusPill value={ticket.severity} /></td>
                      <td>{ticket.channel}</td>
                      <td className="mono">{formatDate(ticket.created_at)}</td>
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
