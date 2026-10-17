// HTTP client: one typed function per route in contracts/API.md §1. Mock mode answers from src/lib/mock.ts.
// Every non-2xx is turned into ApiError(code) so screens can show friendly text (spec §5.2 error body).
import { getMock, getServer } from './config';
import { ApiError } from './errors';
import { mockRequest } from './mock';
import type {
  CheckoutRequest, CheckoutResponse, Club, ClubSummary, EventRequest, FixturesResponse, Inventory, League,
  LoginResponse, MeResponse, OfflineAction, Product, RosterConfig, RosterHistory, Score, Showcase, Standings,
  SyncResponse, TransferRequest,
} from './types';

let token: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setToken(t: string | null) { token = t; }
export function setOnUnauthorized(fn: () => void) { onUnauthorized = fn; }

const TIMEOUT_MS = 8000;

async function request<T>(method: 'GET' | 'POST', path: string, body?: unknown, auth = true): Promise<T> {
  if (getMock()) {
    const r = mockRequest(method, path, body);
    await new Promise((res) => setTimeout(res, 250)); // feel like a network call so loading states show
    if (r.status >= 400) throw new ApiError(r.status, r.body.error.code, r.body.error.details ?? {});
    return r.body as T;
  }
  const headers: Record<string, string> = { 'Content-Type': 'application/json', Accept: 'application/json' };
  if (auth && token) headers.Authorization = `Bearer ${token}`;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(getServer() + path, {
      method, headers, body: body === undefined ? undefined : JSON.stringify(body), signal: ctrl.signal,
    });
  } catch {
    throw new ApiError(0, 'NETWORK');
  } finally {
    clearTimeout(timer);
  }
  let json: any = null;
  try { json = await res.json(); } catch { json = null; }
  if (!res.ok) {
    const code: string = json?.error?.code ?? (res.status >= 500 ? 'INTERNAL_ERROR' : 'VALIDATION_ERROR');
    if (res.status === 401 && auth && onUnauthorized) onUnauthorized();
    throw new ApiError(res.status, code, json?.error?.details ?? {});
  }
  return json as T;
}

const enc = encodeURIComponent;

// --- contract §2 (/api/v1) ---
export const login = (email: string, password: string) =>
  request<LoginResponse>('POST', '/api/v1/auth/login', { email, password }, false);
export const me = () => request<MeResponse>('GET', '/api/v1/me');
export const listLeagues = () => request<{ leagues: League[] }>('GET', '/api/v1/leagues');
export const listFixtures = (leagueId: string) =>
  request<FixturesResponse>('GET', `/api/v1/leagues/${enc(leagueId)}/fixtures`);
export const listClubs = () => request<{ clubs: ClubSummary[] }>('GET', '/api/v1/clubs');
export const getClub = (clubId: string) => request<Club>('GET', `/api/v1/clubs/${enc(clubId)}`);
export const listProducts = () => request<{ products: Product[] }>('GET', '/api/v1/products');
export const getShowcase = (matchId: string) => request<Showcase>('GET', `/api/v1/matches/${enc(matchId)}/showcase`);
export const pinShowcase = (matchId: string, productId: string) =>
  request<Showcase>('POST', `/api/v1/matches/${enc(matchId)}/showcase`, { product_id: productId });
export const getRosterConfig = (leagueId: string) =>
  request<RosterConfig>('GET', `/api/v1/leagues/${enc(leagueId)}/roster-config`);
export const postTransfer = (body: TransferRequest) => request<any>('POST', '/api/v1/roster/transfer', body);
export const postEvent = (body: EventRequest) => request<any>('POST', '/api/v1/events', body);
export const postCheckout = (body: CheckoutRequest) => request<CheckoutResponse>('POST', '/api/v1/checkout', body);
export const postOfflineSync = (device_id: string, actions: OfflineAction[]) =>
  request<SyncResponse>('POST', '/api/v1/offline-sync', { device_id, actions });
export const ping = () => request<{ pong: boolean }>('GET', '/api/v1/ping', undefined, false);

// --- spec §5 reads the app calls directly (no auth) ---
export const getScore = (matchId: string) => request<Score>('GET', `/audit/v1/score/${enc(matchId)}`, undefined, false);
export const getStandings = (leagueId: string) =>
  request<Standings>('GET', `/audit/v1/standings/${enc(leagueId)}`, undefined, false);
export const getInventory = (variantId: string) =>
  request<Inventory>('GET', `/audit/v1/inventory/${enc(variantId)}`, undefined, false);
export const getRosterHistory = (playerId: string) =>
  request<RosterHistory>('GET', `/audit/v1/roster/history/${enc(playerId)}`, undefined, false);
