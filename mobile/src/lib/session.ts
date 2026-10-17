// Logged-in session: token in expo-secure-store (Android Keystore — spec §8.1), user + tenant in memory.
// Restores on app start via GET /api/v1/me; keeps the cached user when offline so cached screens still open.
import * as SecureStore from 'expo-secure-store';
import { useSyncExternalStore } from 'react';
import * as api from './api';
import { ApiError } from './errors';
import { kvGet, kvSet } from './db';
import type { Tenant, User } from './types';

type State = { ready: boolean; token: string | null; user: User | null; tenant: Tenant | null };
let state: State = { ready: false, token: null, user: null, tenant: null };
const listeners = new Set<() => void>();
function set(patch: Partial<State>) {
  state = { ...state, ...patch };
  listeners.forEach((l) => l());
}

export function useSession() {
  return useSyncExternalStore((l) => { listeners.add(l); return () => listeners.delete(l); }, () => state);
}
export const getSession = () => state;

const TOKEN_KEY = 'nascon_token';

export async function signIn(email: string, password: string) {
  const res = await api.login(email.trim().toLowerCase(), password);
  await SecureStore.setItemAsync(TOKEN_KEY, res.token);
  api.setToken(res.token);
  kvSet('session_profile', JSON.stringify({ user: res.user, tenant: res.tenant }));
  set({ token: res.token, user: res.user, tenant: res.tenant });
}

export async function signOut() {
  await SecureStore.deleteItemAsync(TOKEN_KEY);
  api.setToken(null);
  kvSet('session_profile', '');
  set({ token: null, user: null, tenant: null });
}

/** Called once at startup. */
export async function restore() {
  api.setOnUnauthorized(() => { signOut(); });
  try {
    const token = await SecureStore.getItemAsync(TOKEN_KEY);
    if (!token) return set({ ready: true });
    api.setToken(token);
    const cached = kvGet('session_profile');
    if (cached) {
      const p = JSON.parse(cached);
      set({ token, user: p.user, tenant: p.tenant }); // works offline
    }
    try {
      const me = await api.me();
      kvSet('session_profile', JSON.stringify(me));
      set({ token, user: me.user, tenant: me.tenant });
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) await signOut();
      else if (!cached) await signOut();
    }
  } finally {
    set({ ready: true });
  }
}
