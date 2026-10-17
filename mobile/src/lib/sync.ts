// Offline queue + network status + auto-sync (NFR-4, spec §5.14 / §8.4).
// Actions are stored in SQLite in the exact §5.14 format, so they survive force-close; on reconnect they are
// sent to POST /api/v1/offline-sync and each result is kept (sync_log) to explain it in plain language.
import NetInfo from '@react-native-community/netinfo';
import { useSyncExternalStore } from 'react';
import * as api from './api';
import { getMock } from './config';
import { db, deviceId, newId, nowIso } from './db';
import { ApiError, friendlyError } from './errors';
import type { EventRequest, OfflineAction, SyncResult, TransferRequest } from './types';

export type NetMode = 'online' | 'offline' | 'syncing';
export interface QueuedItem { action: OfflineAction; label: string }
export interface LoggedResult { action_id: string; label: string; status: string; error_code: string | null; synced_at: string }

type State = { mode: NetMode; pending: QueuedItem[]; lastResults: LoggedResult[]; lastSyncError: string | null };
let state: State = { mode: 'online', pending: [], lastResults: [], lastSyncError: null };
const listeners = new Set<() => void>();
function set(patch: Partial<State>) { state = { ...state, ...patch }; listeners.forEach((l) => l()); }
export function useSync() {
  return useSyncExternalStore((l) => { listeners.add(l); return () => listeners.delete(l); }, () => state);
}
export const isOffline = () => state.mode === 'offline';

function loadQueue() {
  const rows = db.getAllSync<{ action_json: string; label: string }>('SELECT action_json, label FROM queue ORDER BY created_at, rowid');
  const logs = db.getAllSync<LoggedResult>('SELECT * FROM sync_log ORDER BY synced_at DESC LIMIT 20');
  set({ pending: rows.map((r) => ({ action: JSON.parse(r.action_json), label: r.label })), lastResults: logs });
}

/** Adds one action (spec §5.14 format) to the persistent queue. */
export function enqueue(type: OfflineAction['type'], base_version: number, payload: EventRequest | TransferRequest, label: string) {
  const action: OfflineAction = { action_id: newId('act'), type, queued_at: nowIso(), base_version, payload };
  db.runSync('INSERT INTO queue (action_id, action_json, label, created_at) VALUES (?, ?, ?, ?)', action.action_id, JSON.stringify(action), label, new Date().toISOString());
  loadQueue();
  return action;
}

export function removeQueued(actionId: string) {
  db.runSync('DELETE FROM queue WHERE action_id = ?', actionId);
  loadQueue();
}

/** Plain-language line for one sync result. */
export function describeResult(r: { status: string; error_code: string | null }): string {
  if (r.status === 'applied') return 'Saved on the server.';
  if (r.status === 'duplicate') return 'Already on the server — nothing changed.';
  return 'Not saved: ' + friendlyError(r.error_code);
}

let syncing = false;
/** Sends every queued action. Safe to call often; does nothing when empty or offline. */
export async function syncNow(): Promise<SyncResult[] | null> {
  if (syncing || state.pending.length === 0 || state.mode === 'offline') return null;
  syncing = true;
  set({ mode: 'syncing', lastSyncError: null });
  const items = state.pending.slice(0, 100); // spec: 1–100 actions per request
  try {
    const res = await api.postOfflineSync(deviceId(), items.map((i) => i.action));
    const at = nowIso();
    for (const r of res.results) {
      const label = items.find((i) => i.action.action_id === r.action_id)?.label ?? r.action_id;
      db.runSync('INSERT OR REPLACE INTO sync_log (action_id, label, status, error_code, synced_at) VALUES (?, ?, ?, ?, ?)', r.action_id, label, r.status, r.error_code, at);
      db.runSync('DELETE FROM queue WHERE action_id = ?', r.action_id); // every status is final (§5.14)
    }
    loadQueue();
    set({ mode: 'online' });
    return res.results;
  } catch (e) {
    const offline = e instanceof ApiError && e.code === 'NETWORK';
    set({ mode: offline ? 'offline' : 'online', lastSyncError: e instanceof ApiError ? e.message : friendlyError(null) });
    return null;
  } finally {
    syncing = false;
  }
}

/** Marks the app offline after a network failure seen by any screen. */
export function reportNetworkFailure() { if (!getMock()) set({ mode: 'offline' }); }

async function checkServer() {
  if (getMock()) { if (state.mode === 'offline') set({ mode: 'online' }); return; }
  try {
    await api.ping();
    if (state.mode === 'offline') set({ mode: 'online' });
    if (state.pending.length) syncNow();
  } catch (e) {
    // 429 still means the server is reachable
    if (e instanceof ApiError && e.code !== 'NETWORK') { if (state.mode === 'offline') set({ mode: 'online' }); }
    else set({ mode: 'offline' });
  }
}

let started = false;
export function startSync() {
  if (started) return;
  started = true;
  loadQueue();
  NetInfo.addEventListener((s) => {
    if (s.isConnected === false) set({ mode: 'offline' });
    else checkServer(); // reconnect → confirm server → auto-sync
  });
  setInterval(checkServer, 10000); // airplane mode off but server unreachable (wrong IP) is caught here
  checkServer();
}
