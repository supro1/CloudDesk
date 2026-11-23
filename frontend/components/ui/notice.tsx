import { ApiError, NetworkError } from "@/lib/api";

type NoticeProps = {
  error: ApiError | NetworkError;
  onRetry: () => void;
};

export function Notice({ error, onRetry }: NoticeProps) {
  return (
    <div className="notice" role="alert">
      <div>
        <div className="notice-title">
          {error instanceof NetworkError ? "Connection problem" : "The request could not be completed"}
        </div>
        <div>{error.message}</div>
        {error instanceof ApiError && error.requestId && (
          <div className="helper-text">Request ID: {error.requestId}</div>
        )}
      </div>
      <button className="button" onClick={onRetry} type="button">Try again</button>
    </div>
  );
}
