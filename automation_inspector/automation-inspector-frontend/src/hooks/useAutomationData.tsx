import { useEffect, useState, useCallback } from "react";
import { fetchDependencyMap } from "../API";
import type { DependencyMap } from "../utils/types";
import { UseAutomationDataResult } from "../utils/types";

export function useAutomationData(): UseAutomationDataResult {
  const [data, setData] = useState<DependencyMap | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async (force = false) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDependencyMap(force);
      setData(data);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Unknown error");
      }
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const refresh = useCallback(
    (force = false) => {
      fetchData(force);
    },
    [fetchData],
  );

  return { data, loading, error, refresh };
}
