"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, NetworkError } from "@/lib/api";

export function useApiData<T>(load: () => Promise<T>) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<ApiError | NetworkError>();
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const runId = useRef(0);

  const retry = useCallback(() => {
    setError(undefined);
    setLoading(true);
    setAttempt((value) => value + 1);
  }, []);

  useEffect(() => {
    const run = ++runId.current;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let didAutoRetry = false;

    const execute = () => {
      load()
        .then((result) => {
          if (runId.current !== run) return;
          setData(result);
          setError(undefined);
          setLoading(false);
        })
        .catch((reason: unknown) => {
          if (runId.current !== run) return;
          const nextError = reason instanceof ApiError || reason instanceof NetworkError
            ? reason
            : new NetworkError("Something unexpected happened while loading this page.");
          setError(nextError);
          setLoading(false);
          if (nextError instanceof NetworkError && !didAutoRetry) {
            didAutoRetry = true;
            retryTimer = setTimeout(execute, 1800);
          }
        });
    };

    setLoading(true);
    execute();
    return () => {
      runId.current += 1;
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [load, attempt]);

  return { data, error, loading, retry };
}
