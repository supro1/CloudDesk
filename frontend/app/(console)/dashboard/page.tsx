"use client";

import { useCallback } from "react";
import { PageHeading } from "@/components/ui/page-heading";
import { Notice } from "@/components/ui/notice";
import { useApiData } from "@/lib/use-api-data";
import { listCustomers, listEscalations, listKnowledge, listTickets } from "@/lib/api";

export default function DashboardPage() {
  const loadSummary = useCallback(async () => {
    const [tickets, customers, articles, escalations] = await Promise.all([
      listTickets({ limit: 1 }),
      listCustomers({ limit: 1 }),
      listKnowledge({ limit: 1 }),
      listEscalations({ limit: 1 }),
    ]);
    return {
      tickets: tickets.total,
      customers: customers.total,
      articles: articles.total,
      escalations: escalations.total,
    };
  }, []);
  const { data, error, retry, loading } = useApiData(loadSummary);
  const cards: { label: string; count: number | undefined }[] = [
    { label: "Tickets", count: data?.tickets },
    { label: "Customers", count: data?.customers },
    { label: "Knowledge articles", count: data?.articles },
    { label: "Escalations", count: data?.escalations },
  ];

  return (
    <>
      <PageHeading
        eyebrow="Support operations"
        title="Overview"
        description="A read-only snapshot of the records available to your support team."
      />
      {error && <Notice error={error} onRetry={retry} />}
      <section className="cards" aria-label="Record totals">
        {cards.map(({ label, count }) => (
          <article className="metric-card" key={label}>
            <div className="metric-label">{label}</div>
            <div className="metric-value">{loading && count === undefined ? "—" : count ?? "—"}</div>
            <div className="metric-foot">Records currently available</div>
          </article>
        ))}
      </section>
      <section className="panel" style={{ padding: 22 }}>
        <div className="eyebrow">Console</div>
        <h2 style={{ margin: "8px 0", fontSize: 17 }}>Your support workspace</h2>
        <p className="page-description" style={{ margin: 0 }}>
          Use the navigation to browse tickets, customer accounts, help articles,
          and escalations. This phase provides read-only views; workflow actions
          are introduced in the ticket workflow phase.
        </p>
      </section>
    </>
  );
}
