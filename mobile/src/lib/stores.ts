// Small shared stores: selected league (Fixtures + Standings) and the shopping cart (Store flow, FR-2.3).
import { useSyncExternalStore } from 'react';
import { kvGet, kvSet } from './db';
import type { League, Product, Variant } from './types';

function store<S>(initial: S) {
  let s = initial;
  const ls = new Set<() => void>();
  return {
    get: () => s,
    set: (v: S) => { s = v; ls.forEach((l) => l()); },
    use: () => useSyncExternalStore((l) => { ls.add(l); return () => ls.delete(l); }, () => s),
  };
}

// --- league ---
const leagueStore = store<{ leagueId: string | null; leagues: League[] }>({ leagueId: kvGet('league_id'), leagues: [] });
export const useLeague = leagueStore.use;
export function setLeagues(leagues: League[], preferred: string | null) {
  const cur = leagueStore.get().leagueId;
  const keep = leagues.find((l) => l.league_id === cur) ? cur : null;
  const id = keep ?? (leagues.find((l) => l.league_id === preferred) ? preferred : leagues[0]?.league_id ?? null);
  if (id) kvSet('league_id', id);
  leagueStore.set({ leagueId: id, leagues });
}
export function chooseLeague(id: string) {
  kvSet('league_id', id);
  leagueStore.set({ ...leagueStore.get(), leagueId: id });
}

// --- cart ---
export interface CartLine { product: Product; variant: Variant; quantity: number }
const cartStore = store<CartLine[]>([]);
export const useCart = cartStore.use;
export function addToCart(product: Product, variant: Variant, quantity: number) {
  const lines = cartStore.get();
  const i = lines.findIndex((l) => l.variant.variant_id === variant.variant_id);
  if (i >= 0) {
    const next = [...lines];
    next[i] = { ...next[i], quantity: Math.min(10, next[i].quantity + quantity) }; // spec: quantity 1..10
    cartStore.set(next);
  } else cartStore.set([...lines, { product, variant, quantity }].slice(0, 10)); // spec: 1–10 items
}
export function setQty(variantId: string, q: number) {
  cartStore.set(cartStore.get().map((l) => (l.variant.variant_id === variantId ? { ...l, quantity: q } : l)).filter((l) => l.quantity > 0));
}
export const clearCart = () => cartStore.set([]);
export const cartTotal = (lines: CartLine[]) => lines.reduce((s, l) => s + l.variant.price_minor * l.quantity, 0);
