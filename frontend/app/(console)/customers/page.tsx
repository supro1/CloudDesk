"use client";

import { useCallback, useState } from "react";
import { EmptyState } from "@/components/ui/empty-state";
import { Notice } from "@/components/ui/notice";
import { PageHeading } from "@/components/ui/page-heading";
import { PaginationControls } from "@/components/ui/pagination-controls";
import { listCustomers } from "@/lib/api";
import { useApiData } from "@/lib/use-api-data";
import { formatDate } from "@/lib/format";

const PAGE_SIZE = 20;

export default function CustomersPage() {
  const [offset, setOffset] = useState(0);
  const load = useCallback(() => listCustomers({ limit: PAGE_SIZE, offset }), [offset]);
  const { data, error, loading, retry } = useApiData(load);

  return (
    <>
      <PageHeading eyebrow="Directory" title="Customers" description="Find customer accounts and their organization details." />
      {error && <Notice error={error} onRetry={retry} />}
      <section className="panel" aria-label="Customer list">
        {loading && !data ? <div className="loading-state">Loading customers…</div> : !data?.items.length ? (
          <EmptyState title="No customers yet" message="Customer accounts will appear here when they are available." />
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Customer</th><th>Company</th><th>Customer ID</th><th>Added</th></tr></thead>
                <tbody>
                  {data.items.map((customer) => (
                    <tr key={customer.id}>
                      <td><div className="primary-cell">{customer.name}</div><div className="secondary-cell">{customer.email}</div></td>
                      <td>{customer.company_name ?? <span className="muted">Individual account</span>}</td>
                      <td className="mono muted">{customer.id.slice(0, 8)}…</td>
                      <td className="mono">{formatDate(customer.created_at)}</td>
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
