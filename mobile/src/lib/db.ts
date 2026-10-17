// Local SQLite database: settings (kv), read cache, and the persistent offline queue. NFR-4 / spec §8.4.
import * as SQLite from 'expo-sqlite';

export const db = SQLite.openDatabaseSync('nascon.db');

db.execSync(`
  PRAGMA journal_mode = WAL;
  CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY NOT NULL, json TEXT NOT NULL, saved_at TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS queue (
    action_id TEXT PRIMARY KEY NOT NULL,
    action_json TEXT NOT NULL,      -- the exact spec §5.14 action object
    label TEXT NOT NULL,            -- human description shown in the UI
    created_at TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS sync_log (
    action_id TEXT PRIMARY KEY NOT NULL,
    label TEXT NOT NULL,
    status TEXT NOT NULL,
    error_code TEXT,
    synced_at TEXT NOT NULL
  );
`);

export function kvGet(key: string): string | null {
  const row = db.getFirstSync<{ value: string }>('SELECT value FROM kv WHERE key = ?', key);
  return row ? row.value : null;
}

export function kvSet(key: string, value: string) {
  db.runSync('INSERT OR REPLACE INTO kv (key, value) VALUES (?, ?)', key, value);
}

export function cacheGet<T>(key: string): { data: T; saved_at: string } | null {
  const row = db.getFirstSync<{ json: string; saved_at: string }>('SELECT json, saved_at FROM cache WHERE key = ?', key);
  return row ? { data: JSON.parse(row.json) as T, saved_at: row.saved_at } : null;
}

export function cacheSet(key: string, data: unknown) {
  db.runSync('INSERT OR REPLACE INTO cache (key, json, saved_at) VALUES (?, ?, ?)', key, JSON.stringify(data), nowIso());
}

/** UTC timestamp in the spec format YYYY-MM-DDTHH:MM:SSZ (no milliseconds). */
export function nowIso(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}

/** Today's local date as YYYY-MM-DD. */
export function today(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** Client id safe for the spec id charset A-Za-z0-9_.:- */
export function newId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

/** One id per installation, used as offline-sync device_id. */
export function deviceId(): string {
  let id = kvGet('device_id');
  if (!id) {
    id = newId('dev');
    kvSet('device_id', id);
  }
  return id;
}
