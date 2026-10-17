// TypeScript shapes copied from contracts/API.md §2 and spec §5.9–5.14 (field names character-for-character).
export type Role = 'super_admin' | 'league_organizer' | 'club_manager' | 'player' | 'viewer';

export interface User {
  user_id: string; email: string; display_name: string; role: Role;
  tenant_id: string | null; league_id: string | null; club_id: string | null; player_id: string | null;
}
export interface Tenant {
  tenant_id: string; name: string; primary_color: string; accent_color: string; logo_url: string | null;
}
export interface LoginResponse { token: string; user: User; tenant: Tenant | null }
export interface MeResponse { user: User; tenant: Tenant | null }

export interface TeamRef { team_id: string; name: string }
export interface League {
  league_id: string; tenant_id: string; name: string; sport_id: string | null; season: string; teams: TeamRef[];
}
export type MatchStatus = 'upcoming' | 'in_progress' | 'completed';
export interface Fixture {
  match_id: string; round: number | null; home: TeamRef; away: TeamRef; status: MatchStatus;
  scheduled_at: string | null; venue: string | null; home_score: number | null; away_score: number | null; version: number;
}
export interface FixturesResponse { league_id: string; sport_id: string | null; fixtures: Fixture[] }

export interface ScoreSide {
  team_id: string; score: number; wickets: number | null; balls: number | null; overs: string | null; fair_play: number;
}
export interface MatchEvent {
  sequence: number; event_id: string; type: string; payload: Record<string, any>;
  signature: string; compensated: boolean; compensated_by: string | null;
}
export interface Score {
  match_id: string; sport_id: string; league_id: string | null; status: MatchStatus;
  outcome: 'pending' | 'home_win' | 'away_win' | 'draw' | 'undecided';
  winner_team_id: string | null; tiebreak_winner_team_id: string | null;
  home: ScoreSide; away: ScoreSide; version: number; events: MatchEvent[];
}

export type QualStatus = 'clinched' | 'eliminated' | 'still_possible';
export interface StandingRow {
  rank: number; team_id: string; played: number; won: number; drawn: number; lost: number;
  scored: number; conceded: number; diff: number; points: number; fair_play: number;
  status: QualStatus; resolved_by: string | null;
}
export interface Standings { league_id: string; sport_id: string; qualification_spots: number; table: StandingRow[] }

export interface ClubSummary { club_id: string; tenant_id: string; name: string; short_name: string; primary_color: string }
export interface RosterPlayer {
  player_id: string; name: string; position: string | null; role: string; league_id: string; squad_id: string;
  registration_type: 'initial' | 'transfer' | 'loan'; parent_squad_id: string | null;
}
export interface Club extends ClubSummary {
  home_venue: { name: string; city: string; lat: number; lng: number } | null;
  socials: { instagram: string | null; x: string | null; facebook: string | null };
  staff: { name: string; role: string }[];
  stats: { season: string; played: number; won: number; drawn: number; lost: number; trophies: number }[];
  roster: RosterPlayer[];
}

export interface Variant {
  variant_id: string; size: string | null; color: string | null; price_minor: number; currency: string; stock: number;
}
export interface Product {
  product_id: string; tenant_id: string; club_id: string; name: string;
  category: 'apparel' | 'accessory' | 'digital'; description: string; image_url: string | null; variants: Variant[];
}
export interface Showcase { match_id: string; product: Product | null; pinned_at: string | null }
export interface Inventory { variant_id: string; stock: number; reserved: number }

export interface CheckoutRequest {
  order_id: string; customer_id: string; items: { variant_id: string; quantity: number }[];
  discount_code: string | null; payment: { token: string };
}
export interface CheckoutResponse {
  order_id: string; status: string; currency: string;
  items: { variant_id: string; quantity: number; unit_price_minor: number }[];
  subtotal_minor: number; discount_minor: number; total_minor: number;
  payment: { authorization_id: string; capture_id: string; state: string };
  receipt: { payload: Record<string, any>; signature: string; pdf_base64: string };
}

export interface RosterConfig {
  league_id: string; transfer_window: { open: string; close: string }; max_squad_size: number;
  required_positions: Record<string, number>;
  squads: { squad_id: string; club_id: string; name: string; player_count: number }[];
}
export interface TransferRequest {
  request_id: string; league_id: string; player_id: string; type: 'transfer' | 'loan' | 'release';
  from_squad_id: string; to_squad_id: string | null; effective_date: string; loan_end_date: string | null;
  reason: string; requested_by: string;
}
export interface RosterHistory {
  player_id: string; as_of: string; league_id: string; current_squad_id: string | null;
  parent_squad_id: string | null; history: Record<string, any>[];
}
export interface EventRequest { event_id: string; match_id: string; type: string; payload: Record<string, any> }

// Spec §5.14 action format — stored exactly like this in the offline queue.
export interface OfflineAction {
  action_id: string; type: 'score_event' | 'roster_transfer'; queued_at: string; base_version: number;
  payload: EventRequest | TransferRequest;
}
export interface SyncResult {
  action_id: string; status: 'applied' | 'rejected' | 'duplicate';
  resolution: 'appended' | 'rebased_append' | 'skipped_duplicate' | 'server_wins';
  error_code: string | null; processed_order: number; server_version: number; signature: string | null;
}
export interface SyncResponse {
  device_id: string; results: SyncResult[]; summary: { applied: number; rejected: number; duplicate: number };
}
