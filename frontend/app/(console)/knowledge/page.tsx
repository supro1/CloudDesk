"use client";

import { useCallback, useState } from "react";
import { EmptyState } from "@/components/ui/empty-state";
import { Notice } from "@/components/ui/notice";
import { PageHeading } from "@/components/ui/page-heading";
import { PaginationControls } from "@/components/ui/pagination-controls";
import { StatusPill } from "@/components/ui/status-pill";
import { listKnowledge } from "@/lib/api";
import { useApiData } from "@/lib/use-api-data";

const PAGE_SIZE = 20;

export default function KnowledgePage() {
  const [offset, setOffset] = useState(0);
  const load = useCallback(() => listKnowledge({ limit: PAGE_SIZE, offset }), [offset]);
  const { data, error, loading, retry } = useApiData(load);

  return (
    <>
      <PageHeading eyebrow="Reference library" title="Knowledge" description="Browse the published guidance used to support customers." />
      {error && <Notice error={error} onRetry={retry} />}
      <section className="panel" aria-label="Knowledge articles">
        {loading && !data ? <div className="loading-state">Loading articles…</div> : !data?.items.length ? (
          <EmptyState title="No articles available" message="Published knowledge articles will appear here." />
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Article</th><th>Category</th><th>Tags</th><th>Last updated</th></tr></thead>
                <tbody>
                  {data.items.map((article) => (
                    <tr key={article.id}>
                      <td>
                        <div className="primary-cell">{article.title}</div>
                        <div className="article-summary">{article.summary}</div>
                      </td>
                      <td><StatusPill value={article.category} /></td>
                      <td>{article.tags.length ? article.tags.join(", ") : <span className="muted">—</span>}</td>
                      <td className="mono">{new Date(article.updated_at).toLocaleDateString()}</td>
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
