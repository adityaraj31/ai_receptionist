import {
  type DependencyList,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import { getErrorMessage } from "./errors";

export function useApi<T>(loader: () => Promise<T>, deps: DependencyList) {
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await loaderRef.current();
      setData(result);
      return result;
    } catch (caught) {
      setError(getErrorMessage(caught));
      return null;
    } finally {
      setLoading(false);
    }
  }, deps);

  useEffect(() => {
    void load();
  }, [load]);

  return { data, loading, error, reload: load, setData };
}
