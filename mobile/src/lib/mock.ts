// In-memory mock of the contract routes (contracts/API.md + spec §5) so the app works before the backend is up.
// Shapes copy the contract examples. Only used when Settings → "Use sample data" is on. Not domain logic.
import type { Club, Fixture, MatchEvent, Product, Score, Standings } from './types';

type R = { status: number; body: any };
const err = (status: number, code: string): R => ({ status, body: { error: { code, message: code, details: {} } } });

const TENANT = { tenant_id: 'tenant-alpha', name: 'Alpha Sports', primary_color: '#B8482A', accent_color: '#FFB020', logo_url: null };
const USERS: Record<string, any> = {
  'admin@nascon.test': { user_id: 'user-admin', display_name: 'Platform Admin', role: 'super_admin', tenant_id: null, league_id: null, club_id: null, player_id: null },
  'organizer@nascon.test': { user_id: 'user-organizer', display_name: 'League Organizer', role: 'league_organizer', tenant_id: 'tenant-alpha', league_id: 'league-alpha-1', club_id: null, player_id: null },
  'manager@nascon.test': { user_id: 'user-manager', display_name: 'Club Manager', role: 'club_manager', tenant_id: 'tenant-alpha', league_id: null, club_id: 'club-alpha-1', player_id: null },
  'player@nascon.test': { user_id: 'user-player', display_name: 'Ali Khan', role: 'player', tenant_id: 'tenant-alpha', league_id: null, club_id: 'club-alpha-1', player_id: 'player-alpha-1' },
  'viewer@nascon.test': { user_id: 'user-viewer', display_name: 'General Viewer', role: 'viewer', tenant_id: 'tenant-alpha', league_id: null, club_id: null, player_id: null },
};
let currentEmail = 'viewer@nascon.test';

const CLUBS = [
  { club_id: 'club-alpha-1', name: 'Alpha United', short_name: 'AUN', primary_color: '#0B5FFF' },
  { club_id: 'club-alpha-2', name: 'Alpha Rovers', short_name: 'ARO', primary_color: '#2f6b53' },
  { club_id: 'demo-club-alpha-3', name: 'Margalla FC', short_name: 'MFC', primary_color: '#6b3f8c' },
  { club_id: 'demo-club-alpha-4', name: 'Rawal City', short_name: 'RCY', primary_color: '#8a5a1e' },
].map((c) => ({ ...c, tenant_id: 'tenant-alpha' }));
const name = (id: string) => CLUBS.find((c) => c.club_id === id)?.name ?? id;

const NAMES = ['Ali Khan', 'Bilal Ahmed', 'Hamza Raza', 'Usman Tariq', 'Saad Iqbal', 'Fahad Malik', 'Zain Abbas', 'Omer Siddiqui', 'Hassan Javed', 'Danish Shah', 'Imran Qureshi', 'Talha Butt'];
const POS = ['gk', 'gk', 'df', 'df', 'df', 'df', 'mf', 'mf', 'mf', 'fw', 'fw', 'fw'];
const ROLE = ['captain', 'substitute', 'vice_captain', 'starter', 'starter', 'substitute', 'starter', 'starter', 'substitute', 'starter', 'starter', 'substitute'];
const players: Record<string, { player_id: string; name: string; position: string; role: string; squad_id: string | null; type: string; history: any[] }> = {};
CLUBS.forEach((c, ci) => NAMES.forEach((n, i) => {
  const id = ci === 0 && i === 0 ? 'player-alpha-1' : ci === 1 && i === 0 ? 'player-alpha-2' : `demo-p-${ci}-${i}`;
  players[id] = { player_id: id, name: ci === 0 ? n : NAMES[(i + ci * 3) % 12].split(' ')[0] + ' ' + NAMES[(i + ci * 5) % 12].split(' ')[1], position: POS[i], role: ROLE[i], squad_id: c.club_id, type: 'initial', history: [] };
}));

const fixtures: Fixture[] = [];
const pairs = [[0, 1], [2, 3], [0, 2], [1, 3], [0, 3], [1, 2]];
pairs.forEach(([h, a], i) => fixtures.push({
  match_id: `demo-m${i + 1}`, round: Math.floor(i / 2) + 1,
  home: { team_id: CLUBS[h].club_id, name: CLUBS[h].name }, away: { team_id: CLUBS[a].club_id, name: CLUBS[a].name },
  status: 'upcoming', scheduled_at: `2026-10-${17 + Math.floor(i / 3)}T${String(9 + (i % 3) * 3).padStart(2, '0')}:00:00Z`,
  venue: ['Alpha Arena', 'Margalla Ground', 'Rawal Stadium'][i % 3], home_score: null, away_score: null, version: 0,
}));
const events: Record<string, MatchEvent[]> = {};
function append(matchId: string, event_id: string, type: string, payload: any) {
  const list = (events[matchId] ??= []);
  if (type === 'compensation') {
    const t = list.find((e) => e.event_id === payload.compensates);
    if (t) { t.compensated = true; t.compensated_by = event_id; }
  }
  list.push({ sequence: list.length + 1, event_id, type, payload, signature: 'mock', compensated: false, compensated_by: null });
}
const goal = (m: string, id: string, team: string) => append(m, id, 'score', { team_id: team, event_type: 'goal' });
['demo-m1', 'demo-m2', 'demo-m3', 'demo-m4'].forEach((m) => append(m, `${m}-e0`, 'match_start', {}));
goal('demo-m1', 'demo-evt-1', 'club-alpha-1'); goal('demo-m1', 'demo-evt-2', 'club-alpha-2'); goal('demo-m1', 'demo-evt-3', 'club-alpha-1');
append('demo-m1', 'demo-evt-4', 'discipline', { team_id: 'club-alpha-2', points: -1 }); append('demo-m1', 'demo-m1-end', 'match_end', {});
goal('demo-m2', 'demo-evt-5', 'demo-club-alpha-3'); goal('demo-m2', 'demo-evt-6', 'demo-club-alpha-4');
append('demo-m2', 'demo-evt-7', 'compensation', { compensates: 'demo-evt-6', reason: 'Offside — VAR review' }); append('demo-m2', 'demo-m2-end', 'match_end', {});
goal('demo-m3', 'demo-evt-8', 'club-alpha-1'); append('demo-m3', 'demo-m3-end', 'match_end', {});
goal('demo-m4', 'demo-evt-9', 'club-alpha-2'); goal('demo-m4', 'demo-evt-10', 'demo-club-alpha-4');

function score(matchId: string): Score | null {
  const f = fixtures.find((x) => x.match_id === matchId);
  if (!f) return null;
  const list = events[matchId] ?? [];
  let hs = 0, as = 0, hf = 0, af = 0, status: Score['status'] = 'upcoming';
  for (const e of list) {
    if (e.type === 'match_start') status = 'in_progress';
    if (e.type === 'match_end') status = 'completed';
    if (e.compensated || e.type === 'compensation') continue;
    if (e.type === 'score') e.payload.team_id === f.home.team_id ? hs++ : as++;
    if (e.type === 'discipline') e.payload.team_id === f.home.team_id ? (hf += e.payload.points) : (af += e.payload.points);
  }
  const outcome = status !== 'completed' ? 'pending' : hs > as ? 'home_win' : as > hs ? 'away_win' : 'draw';
  const side = (team_id: string, s: number, fp: number) => ({ team_id, score: s, wickets: null, balls: null, overs: null, fair_play: fp });
  return {
    match_id: matchId, sport_id: 'football', league_id: 'league-alpha-1', status, outcome,
    winner_team_id: outcome === 'home_win' ? f.home.team_id : outcome === 'away_win' ? f.away.team_id : null,
    tiebreak_winner_team_id: null, home: side(f.home.team_id, hs, hf), away: side(f.away.team_id, as, af),
    version: list.length, events: list.map((e) => ({ ...e })),
  };
}

function standings(): Standings {
  const rows: Record<string, any> = {};
  CLUBS.forEach((c) => (rows[c.club_id] = { team_id: c.club_id, played: 0, won: 0, drawn: 0, lost: 0, scored: 0, conceded: 0, diff: 0, points: 0, fair_play: 0, remaining: 0 }));
  for (const f of fixtures) {
    const s = score(f.match_id)!;
    const h = rows[f.home.team_id], a = rows[f.away.team_id];
    if (s.status !== 'completed') { h.remaining++; a.remaining++; continue; }
    h.played++; a.played++; h.scored += s.home.score; h.conceded += s.away.score; a.scored += s.away.score; a.conceded += s.home.score;
    h.fair_play += s.home.fair_play; a.fair_play += s.away.fair_play;
    if (s.outcome === 'home_win') { h.won++; a.lost++; h.points += 3; } else if (s.outcome === 'away_win') { a.won++; h.lost++; a.points += 3; } else { h.drawn++; a.drawn++; h.points++; a.points++; }
  }
  const list = Object.values(rows).map((r: any) => ({ ...r, diff: r.scored - r.conceded }));
  list.sort((x: any, y: any) => y.points - x.points || y.diff - x.diff || y.scored - x.scored);
  const k = 2;
  const table = list.map((t: any, i: number) => {
    const max = (x: any) => x.points + 3 * x.remaining;
    const others = list.filter((x: any) => x !== t);
    const status = others.filter((x: any) => max(x) >= t.points).length < k ? 'clinched' : others.filter((x: any) => x.points > max(t)).length >= k ? 'eliminated' : 'still_possible';
    const { remaining, ...row } = t;
    return { rank: i + 1, ...row, status, resolved_by: null };
  });
  return { league_id: 'league-alpha-1', sport_id: 'football', qualification_spots: k, table } as Standings;
}

const PRODUCTS: Product[] = [
  { product_id: 'prod-jersey-001', tenant_id: 'tenant-alpha', club_id: 'club-alpha-1', name: 'Home Jersey 2026', category: 'apparel', description: 'Official home kit.', image_url: null,
    variants: [{ variant_id: 'var-jersey-001-M', size: 'M', color: 'Blue', price_minor: 450000, currency: 'PKR', stock: 1 }, { variant_id: 'var-jersey-001-L', size: 'L', color: 'Blue', price_minor: 450000, currency: 'PKR', stock: 5 }] },
  { product_id: 'demo-prod-scarf', tenant_id: 'tenant-alpha', club_id: 'club-alpha-1', name: 'Supporters Scarf', category: 'accessory', description: 'Knitted club scarf.', image_url: null,
    variants: [{ variant_id: 'demo-var-scarf', size: null, color: null, price_minor: 150000, currency: 'PKR', stock: 20 }] },
  { product_id: 'demo-prod-cap', tenant_id: 'tenant-alpha', club_id: 'club-alpha-1', name: 'Club Cap', category: 'accessory', description: 'Adjustable cotton cap.', image_url: null,
    variants: [{ variant_id: 'demo-var-cap-black', size: null, color: 'Black', price_minor: 120000, currency: 'PKR', stock: 10 }, { variant_id: 'demo-var-cap-white', size: null, color: 'White', price_minor: 120000, currency: 'PKR', stock: 10 }] },
  { product_id: 'demo-prod-wallpaper', tenant_id: 'tenant-alpha', club_id: 'club-alpha-1', name: 'Phone Wallpaper Pack', category: 'digital', description: 'Ten HD wallpapers.', image_url: null,
    variants: [{ variant_id: 'demo-var-wallpaper', size: null, color: null, price_minor: 30000, currency: 'PKR', stock: 999 }] },
];
const findVariant = (id: string) => PRODUCTS.flatMap((p) => p.variants).find((v) => v.variant_id === id);
const showcase: Record<string, { product_id: string; pinned_at: string }> = { 'demo-m4': { product_id: 'prod-jersey-001', pinned_at: '2026-10-17T09:00:00Z' } };
const orders: Record<string, any> = {};
// Minimal valid one-page PDF so receipt sharing works in mock mode.
const PDF_B64 = 'JVBERi0xLjQKMSAwIG9iajw8L1R5cGUvQ2F0YWxvZy9QYWdlcyAyIDAgUj4+ZW5kb2JqCjIgMCBvYmo8PC9UeXBlL1BhZ2VzL0tpZHNbMyAwIFJdL0NvdW50IDE+PmVuZG9iagozIDAgb2JqPDwvVHlwZS9QYWdlL1BhcmVudCAyIDAgUi9NZWRpYUJveFswIDAgMzAwIDE1MF0vQ29udGVudHMgNCAwIFIvUmVzb3VyY2VzPDwvRm9udDw8L0YxIDUgMCBSPj4+Pj4+ZW5kb2JqCjQgMCBvYmo8PC9MZW5ndGggNDk+PnN0cmVhbQpCVCAvRjEgMTggVGYgMzAgNzAgVGQgKFNhbXBsZSByZWNlaXB0KSBUaiBFVAplbmRzdHJlYW0KZW5kb2JqCjUgMCBvYmo8PC9UeXBlL0ZvbnQvU3VidHlwZS9UeXBlMS9CYXNlRm9udC9IZWx2ZXRpY2E+PmVuZG9iagp0cmFpbGVyPDwvUm9vdCAxIDAgUj4+CiUlRU9G';

function club(id: string): Club | null {
  const c = CLUBS.find((x) => x.club_id === id);
  if (!c) return null;
  return {
    ...c,
    home_venue: { name: id === 'club-alpha-1' ? 'Alpha Arena' : `${c.name} Ground`, city: 'Islamabad', lat: 33.6844, lng: 73.0479 },
    socials: { instagram: '@' + c.name.toLowerCase().replace(/\s/g, ''), x: '@' + c.name.toLowerCase().replace(/\s/g, ''), facebook: null },
    staff: [{ name: 'Usman Tariq', role: 'coach' }, { name: 'Sana Mir', role: 'manager' }, { name: 'Dr. Ayesha Noor', role: 'physio' }],
    stats: [{ season: '2025', played: 18, won: 11, drawn: 4, lost: 3, trophies: 1 }, { season: '2024', played: 18, won: 8, drawn: 5, lost: 5, trophies: 0 }],
    roster: Object.values(players).filter((p) => p.squad_id === id).map((p) => ({
      player_id: p.player_id, name: p.name, position: p.position, role: p.role, league_id: 'league-alpha-1', squad_id: id,
      registration_type: p.type as any, parent_squad_id: null,
    })),
  };
}

function doEvent(b: any): R {
  const f = fixtures.find((x) => x.match_id === b?.match_id);
  if (!f) return err(404, 'MATCH_NOT_FOUND');
  const s = score(f.match_id)!;
  const list = events[f.match_id] ?? [];
  if (list.some((e) => e.event_id === b.event_id)) return { status: 200, body: { event_id: b.event_id, match_id: f.match_id, type: b.type, sequence: 1, match_version: s.version, signature: 'mock' } };
  if (b.type === 'score' && s.status !== 'in_progress') return err(409, 'MATCH_NOT_IN_PROGRESS');
  if (b.type === 'match_start' && s.status !== 'upcoming') return err(409, 'ILLEGAL_TRANSITION');
  if (b.type === 'match_end' && s.status !== 'in_progress') return err(409, 'ILLEGAL_TRANSITION');
  if (b.type === 'compensation') {
    const t = list.find((e) => e.event_id === b.payload?.compensates);
    if (!t) return err(404, 'EVENT_NOT_FOUND');
    if (t.compensated || !['score', 'discipline', 'tiebreak_winner'].includes(t.type)) return err(409, 'INVALID_COMPENSATION');
  }
  append(f.match_id, b.event_id, b.type, b.payload ?? {});
  const v = events[f.match_id].length;
  return { status: 201, body: { event_id: b.event_id, match_id: f.match_id, type: b.type, sequence: v, match_version: v, signature: 'mock' } };
}

function doTransfer(b: any): R {
  const p = players[b?.player_id];
  if (!p) return err(404, 'PLAYER_NOT_FOUND');
  if (p.squad_id !== b.from_squad_id) return err(409, 'NOT_IN_SQUAD');
  if (b.type !== 'release' && (b.effective_date < '2026-10-01' || b.effective_date > '2026-10-31')) return err(409, 'TRANSFER_WINDOW_CLOSED');
  if (b.type !== 'release' && Object.values(players).filter((x) => x.squad_id === b.to_squad_id).length + 1 > 25) return err(409, 'SQUAD_FULL');
  const gks = Object.values(players).filter((x) => x.squad_id === p.squad_id && x.position === p.position).length;
  if (p.position === 'gk' && gks - 1 < 1) return err(409, 'MIN_POSITION_VIOLATION');
  const entry = { audit_id: `au-${Date.now()}`, action: b.type, player_id: p.player_id, league_id: b.league_id, from_squad_id: b.from_squad_id, to_squad_id: b.to_squad_id, effective_date: b.effective_date, state: 'active', who: b.requested_by, when: new Date().toISOString().replace(/\.\d+Z/, 'Z'), why: b.reason };
  p.history.push(entry);
  p.squad_id = b.type === 'release' ? null : b.to_squad_id;
  p.role = 'substitute'; p.type = b.type === 'loan' ? 'loan' : 'transfer';
  return { status: 201, body: { request_id: b.request_id, status: 'accepted', state: 'active', blocking_match_id: null, registration: null, audit_entry: entry } };
}

export function mockRequest(method: string, path: string, body: any): R {
  const p = path.split('?')[0].split('/').map(decodeURIComponent);
  const route = `${method} ${p.slice(1, 4).join('/')}`;
  if (method === 'POST' && path === '/api/v1/auth/login') {
    const u = USERS[String(body?.email ?? '').toLowerCase()];
    if (!u || body?.password !== 'Nascon@26') return err(401, 'UNAUTHENTICATED');
    currentEmail = body.email.toLowerCase();
    return { status: 200, body: { token: 'mock-token', user: { ...u, email: currentEmail }, tenant: u.tenant_id ? TENANT : null } };
  }
  if (path === '/api/v1/me') { const u = USERS[currentEmail]; return { status: 200, body: { user: { ...u, email: currentEmail }, tenant: u.tenant_id ? TENANT : null } }; }
  if (path === '/api/v1/ping') return { status: 200, body: { pong: true } };
  if (path === '/api/v1/leagues') return { status: 200, body: { leagues: [
    { league_id: 'league-alpha-1', tenant_id: 'tenant-alpha', name: 'Alpha Premier League', sport_id: 'football', season: '2026', teams: CLUBS.map((c) => ({ team_id: c.club_id, name: c.name })) },
    { league_id: 'league-alpha-2', tenant_id: 'tenant-alpha', name: 'Alpha Basketball Cup', sport_id: 'basketball', season: '2026', teams: [] },
  ] } };
  if (route === 'GET api/v1/leagues' && p[5] === 'fixtures') {
    if (p[4] !== 'league-alpha-1') return { status: 200, body: { league_id: p[4], sport_id: 'basketball', fixtures: [] } };
    return { status: 200, body: { league_id: p[4], sport_id: 'football', fixtures: fixtures.map((f) => { const s = score(f.match_id)!; return { ...f, status: s.status, home_score: s.status === 'upcoming' ? null : s.home.score, away_score: s.status === 'upcoming' ? null : s.away.score, version: s.version }; }) } };
  }
  if (route === 'GET api/v1/leagues' && p[5] === 'roster-config') return { status: 200, body: { league_id: p[4], transfer_window: { open: '2026-10-01', close: '2026-10-31' }, max_squad_size: 25, required_positions: { gk: 1 },
    squads: CLUBS.map((c) => ({ squad_id: c.club_id, club_id: c.club_id, name: c.name, player_count: Object.values(players).filter((x) => x.squad_id === c.club_id).length })) } };
  if (path === '/api/v1/clubs') return { status: 200, body: { clubs: CLUBS } };
  if (route === 'GET api/v1/clubs') { const c = club(p[4]); return c ? { status: 200, body: c } : err(404, 'SQUAD_NOT_FOUND'); }
  if (path === '/api/v1/products') return { status: 200, body: { products: PRODUCTS } };
  if (route === 'GET api/v1/matches') { const s = showcase[p[4]]; return { status: 200, body: { match_id: p[4], product: s ? PRODUCTS.find((x) => x.product_id === s.product_id) : null, pinned_at: s?.pinned_at ?? null } }; }
  if (route === 'POST api/v1/matches') { showcase[p[4]] = { product_id: body.product_id, pinned_at: new Date().toISOString().replace(/\.\d+Z/, 'Z') }; return mockRequest('GET', path, null); }
  if (route === 'GET audit/v1/score') { const s = score(p[4]); return s ? { status: 200, body: s } : err(404, 'MATCH_NOT_FOUND'); }
  if (route === 'GET audit/v1/standings') return p[4] === 'league-alpha-1' ? { status: 200, body: standings() } : err(404, 'LEAGUE_NOT_FOUND');
  if (route === 'GET audit/v1/inventory') { const v = findVariant(p[4]); return v ? { status: 200, body: { variant_id: v.variant_id, stock: v.stock, reserved: 0 } } : err(404, 'VARIANT_NOT_FOUND'); }
  if (route === 'GET audit/v1/roster') { const pl = players[p[5]]; return pl ? { status: 200, body: { player_id: pl.player_id, as_of: '2026-10-17', league_id: 'league-alpha-1', current_squad_id: pl.squad_id, parent_squad_id: null, history: pl.history } } : err(404, 'PLAYER_NOT_FOUND'); }
  if (path === '/api/v1/events') return doEvent(body);
  if (path === '/api/v1/roster/transfer') return doTransfer(body);
  if (path === '/api/v1/checkout') {
    if (orders[body.order_id]) return { status: 200, body: orders[body.order_id] };
    if (body.discount_code && body.discount_code !== 'WELCOME10') return err(400, 'INVALID_DISCOUNT_CODE');
    const lines = body.items.map((i: any) => ({ ...i, v: findVariant(i.variant_id) }));
    if (lines.some((l: any) => !l.v)) return err(404, 'VARIANT_NOT_FOUND');
    if (lines.some((l: any) => l.v.stock < l.quantity)) return err(409, 'OUT_OF_STOCK');
    if (body.payment.token === 'tok_declined') return err(402, 'PAYMENT_DECLINED');
    if (body.payment.token === 'tok_capture_fail') return err(402, 'PAYMENT_CAPTURE_FAILED');
    lines.forEach((l: any) => (l.v.stock -= l.quantity));
    const items = lines.map((l: any) => ({ variant_id: l.variant_id, quantity: l.quantity, unit_price_minor: l.v.price_minor }));
    const subtotal = items.reduce((s: number, i: any) => s + i.quantity * i.unit_price_minor, 0);
    const discount = body.discount_code ? Math.floor((subtotal * 10) / 100) : 0;
    const totals = { subtotal_minor: subtotal, discount_minor: discount, total_minor: subtotal - discount };
    const res = { order_id: body.order_id, status: 'paid', currency: 'PKR', items, ...totals, payment: { authorization_id: 'auth_1', capture_id: 'cap_1', state: 'captured' },
      receipt: { payload: { order_id: body.order_id, customer_id: body.customer_id, items, ...totals, currency: 'PKR', paid_at: new Date().toISOString().replace(/\.\d+Z/, 'Z') }, signature: 'mock', pdf_base64: PDF_B64 } };
    orders[body.order_id] = res;
    return { status: 201, body: res };
  }
  if (path === '/api/v1/offline-sync') {
    const results = body.actions.map((a: any, i: number) => {
      const r = a.type === 'score_event' ? doEvent(a.payload) : doTransfer(a.payload);
      const ok = r.status < 300;
      return { action_id: a.action_id, status: ok ? 'applied' : 'rejected', resolution: ok ? 'appended' : 'server_wins', error_code: ok ? null : r.body.error.code, processed_order: i + 1, server_version: ok ? r.body.match_version ?? 1 : a.base_version, signature: null };
    });
    return { status: 200, body: { device_id: body.device_id, results, summary: { applied: results.filter((r: any) => r.status === 'applied').length, rejected: results.filter((r: any) => r.status === 'rejected').length, duplicate: 0 } } };
  }
  return err(404, 'MATCH_NOT_FOUND');
}
