// Read-through cache: try the network, save to SQLite; if offline show the cached copy (NFR-4, spec §8.4 step 1–2).
import { useCallback, useEffect, useRef, useState } from 'react';
import { cacheGet, cacheSet } from './db';
import { ApiError, messageOf } from './errors';
import { reportNetworkFailure } from './sync';

export interface Loaded<T> {
  data: T | null; loading: boolean; error: string | null; fromCache: string | null; reload: () => Promise<void>;
}

/** key = cache key (null = do not cache). fetcher runs on mount and on reload(). */
export function useCached<T>(key: string | null, fetcher: () => Promise<T>, deps: unknown[] = []): Loaded<T> {
  const [data, setData] = useState<T | null>(() => (key ? cacheGet<T>(key)?.data ?? null : null));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fromCache, setFromCache] = useState<string | null>(null);
  const alive = useRef(true);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const d = await fetcher();
      if (!alive.current) return;
      if (key) cacheSet(key, d);
      setData(d); setError(null); setFromCache(null);
    } catch (e) {
      if (!alive.current) return;
      if (e instanceof ApiError && e.code === 'NETWORK') reportNetworkFailure();
      const cached = key ? cacheGet<T>(key) : null;
      if (cached) { setData(cached.data); setFromCache(cached.saved_at); setError(null); }
      else setError(messageOf(e));
    } finally {
      if (alive.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, ...deps]);

  useEffect(() => { alive.current = true; reload(); return () => { alive.current = false; }; }, [reload]);
  return { data, loading, error, fromCache, reload };
}
