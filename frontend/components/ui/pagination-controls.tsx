type PaginationControlsProps = {
  total: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
};

export function PaginationControls({ total, limit, offset, onChange }: PaginationControlsProps) {
  const first = total === 0 ? 0 : offset + 1;
  const last = Math.min(offset + limit, total);
  return (
    <div className="pagination">
      <span>Showing {first}–{last} of {total}</span>
      <div className="pagination-actions">
        <button
          className="button"
          type="button"
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - limit))}
        >
          Previous
        </button>
        <button
          className="button"
          type="button"
          disabled={offset + limit >= total}
          onClick={() => onChange(offset + limit)}
        >
          Next
        </button>
      </div>
    </div>
  );
}
