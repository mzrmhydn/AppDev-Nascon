// Shared "send now, or queue if offline" helper for scoring + roster writes (NFR-4, spec §5.14).
// Online → the /api/v1 twin; a network failure (or offline banner) → stored in the SQLite queue as a §5.14 action.
import * as api from './api';
import { ApiError, messageOf } from './errors';
import { enqueue, isOffline, reportNetworkFailure } from './sync';
import type { EventRequest, TransferRequest } from './types';

export type SendResult = { kind: 'sent' | 'queued' | 'error'; text: string; body?: any };

export async function sendOrQueue(type: 'score_event' | 'roster_transfer', baseVersion: number, payload: EventRequest | TransferRequest, label: string): Promise<SendResult> {
  const queue = (): SendResult => {
    enqueue(type, baseVersion, payload, label);
    return { kind: 'queued', text: 'You are offline. Saved on this phone as pending — it will sync automatically when you are back online.' };
  };
  if (isOffline()) return queue();
  try {
    const body = type === 'score_event' ? await api.postEvent(payload as EventRequest) : await api.postTransfer(payload as TransferRequest);
    return { kind: 'sent', text: 'Saved on the server.', body };
  } catch (e) {
    if (e instanceof ApiError && e.code === 'NETWORK') { reportNetworkFailure(); return queue(); }
    return { kind: 'error', text: messageOf(e) };
  }
}
