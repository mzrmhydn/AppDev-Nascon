// Roster management for Club Manager (spec §8.2): transfer / loan / release a player via POST /api/v1/roster/transfer
// (body = spec §5.11). Works offline: queued as a roster_transfer action with base_version = history length (§5.14).
import { Ionicons } from '@expo/vector-icons';
import { useEffect, useMemo, useState } from 'react';
import { Alert, ScrollView, View } from 'react-native';
import * as api from '../../lib/api';
import { cacheGet, cacheSet, newId, today } from '../../lib/db';
import { useSession } from '../../lib/session';
import { palette } from '../../lib/theme';
import type { RosterHistory, TransferRequest } from '../../lib/types';
import { useCached } from '../../lib/useCached';
import { sendOrQueue, SendResult } from '../../lib/writes';
import { CachedNotice, Chip, Empty, ErrorState, Field, HexButton, Loading, Notice, SectionTitle, styles, T } from '../../ui/kit';

type Kind = 'transfer' | 'loan' | 'release';
const KIND_TEXT: Record<Kind, string> = { transfer: 'Transfer (permanent)', loan: 'Loan (temporary)', release: 'Release from league' };

export default function Roster() {
  const { user } = useSession();
  const clubs = useCached('clubs', api.listClubs, [user?.user_id]);
  const [clubId, setClubId] = useState<string | null>(user?.club_id ?? null);
  useEffect(() => { if (!clubId && clubs.data?.clubs.length) setClubId(clubs.data.clubs[0].club_id); }, [clubs.data, clubId]);
  const club = useCached(clubId ? `club:${clubId}` : null, () => api.getClub(clubId!), [clubId]);
  const leagueId = club.data?.roster[0]?.league_id ?? null;
  const cfg = useCached(leagueId ? `roster-config:${leagueId}` : null, () => api.getRosterConfig(leagueId!), [leagueId]);

  const [playerId, setPlayerId] = useState<string | null>(null);
  const [kind, setKind] = useState<Kind>('transfer');
  const [toSquad, setToSquad] = useState<string | null>(null);
  const [date, setDate] = useState(today());
  const [loanEnd, setLoanEnd] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SendResult | null>(null);

  const player = club.data?.roster.find((p) => p.player_id === playerId) ?? null;
  const squads = useMemo(() => (cfg.data?.squads ?? []).filter((s) => s.squad_id !== player?.squad_id), [cfg.data, player]);

  // base_version = number of audit entries of the player (spec §5.14); refreshed online, cached for offline.
  useEffect(() => {
    if (!playerId) return;
    api.getRosterHistory(playerId).then((h) => cacheSet(`history:${playerId}`, h)).catch(() => {});
  }, [playerId]);

  if (!clubs.data && clubs.loading) return <Loading label="Loading roster…" />;
  if (!clubId) return <Empty icon="people-outline" title="No club linked to your account" />;
  if (!club.data && club.loading) return <Loading label="Loading roster…" />;
  if (!club.data) return <ErrorState message={club.error ?? ''} onRetry={club.reload} testID="roster-retry" />;

  const dateOk = /^\d{4}-\d{2}-\d{2}$/.test(date);
  const loanOk = kind !== 'loan' || (/^\d{4}-\d{2}-\d{2}$/.test(loanEnd) && loanEnd > date);
  const ready = !!player && dateOk && loanOk && (kind === 'release' || !!toSquad) && !!leagueId;
  const toName = cfg.data?.squads.find((s) => s.squad_id === toSquad)?.name ?? toSquad;

  async function submit() {
    if (!player || !leagueId) return;
    const body: TransferRequest = {
      request_id: newId('tr'), league_id: leagueId, player_id: player.player_id, type: kind,
      from_squad_id: player.squad_id, to_squad_id: kind === 'release' ? null : toSquad,
      effective_date: date, loan_end_date: kind === 'loan' ? loanEnd : null,
      reason: reason.trim() || KIND_TEXT[kind], requested_by: user?.user_id ?? 'unknown',
    };
    const base = cacheGet<RosterHistory>(`history:${player.player_id}`)?.data.history.length ?? 0;
    const label = `${KIND_TEXT[kind].split(' ')[0]} ${player.name}${kind === 'release' ? '' : ` → ${toName}`}`;
    setBusy(true); setResult(null);
    const r = await sendOrQueue('roster_transfer', base, body, label);
    setResult(r.kind === 'sent' ? { ...r, text: r.body?.state === 'deferred_until_match_end' ? 'Accepted — it takes effect after the player’s current match ends.' : `Done: ${label}.` } : r);
    setBusy(false);
    if (r.kind === 'sent') { club.reload(); cfg.reload(); setPlayerId(null); }
  }

  function confirm() {
    if (!player) return;
    const what = kind === 'release' ? `Release ${player.name} from the league?` : `${KIND_TEXT[kind]}: move ${player.name} to ${toName} from ${date}${kind === 'loan' ? ` until ${loanEnd}` : ''}?`;
    Alert.alert('Please confirm', what, [{ text: 'Cancel', style: 'cancel' }, { text: kind === 'release' ? 'Release' : 'Confirm', style: kind === 'release' ? 'destructive' : 'default', onPress: submit }]);
  }

  return (
    <ScrollView style={styles.page} contentContainerStyle={{ padding: 16, paddingBottom: 40 }} keyboardShouldPersistTaps="handled">
      <T kind="display" accessibilityRole="header" style={{ fontSize: 34 }}>ROSTER</T>
      <T kind="muted">{club.data.name}{cfg.data ? ` · window ${cfg.data.transfer_window.open} → ${cfg.data.transfer_window.close} · max ${cfg.data.max_squad_size}` : ''}</T>
      <CachedNotice savedAt={club.fromCache} />

      {user?.role === 'super_admin' && clubs.data ? (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
          {clubs.data.clubs.map((c) => <Chip key={c.club_id} testID={`roster-club-${c.club_id}`} label={c.short_name || c.name} selected={c.club_id === clubId} onPress={() => { setClubId(c.club_id); setPlayerId(null); }} />)}
        </View>
      ) : null}

      <SectionTitle>1. PLAYER</SectionTitle>
      {club.data.roster.length === 0 ? <T kind="muted">No players in this club.</T> : (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
          {club.data.roster.map((p) => (
            <Chip key={p.player_id} testID={`roster-player-${p.player_id}`} label={p.name} sub={`${(p.position ?? "–").toUpperCase()} · ${(p.role ?? "").replace('_', '-')}${p.registration_type === 'loan' ? ' · on loan' : ''}`}
              selected={p.player_id === playerId} onPress={() => { setPlayerId(p.player_id); setResult(null); }} />
          ))}
        </View>
      )}

      <SectionTitle>2. ACTION</SectionTitle>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
        {(Object.keys(KIND_TEXT) as Kind[]).map((k) => <Chip key={k} testID={`roster-kind-${k}`} label={KIND_TEXT[k]} selected={kind === k} onPress={() => setKind(k)} />)}
      </View>

      {kind !== 'release' ? (
        <>
          <SectionTitle>3. DESTINATION CLUB</SectionTitle>
          {!cfg.data ? <T kind="muted">{cfg.loading ? 'Loading clubs…' : 'Club list not available offline yet — open this screen once while online.'}</T> : (
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
              {squads.map((s) => <Chip key={s.squad_id} testID={`roster-to-${s.squad_id}`} label={s.name} sub={`${s.player_count} players`} selected={toSquad === s.squad_id} onPress={() => setToSquad(s.squad_id)} />)}
            </View>
          )}
        </>
      ) : null}

      <SectionTitle>{kind === 'release' ? '3. DETAILS' : '4. DETAILS'}</SectionTitle>
      <Field label="Effective date (YYYY-MM-DD)" testID="roster-date" value={date} onChangeText={setDate} keyboardType="numbers-and-punctuation" />
      {kind === 'loan' ? <Field label="Loan ends (YYYY-MM-DD, after the start)" testID="roster-loan-end" value={loanEnd} onChangeText={setLoanEnd} keyboardType="numbers-and-punctuation" placeholder="2026-10-31" /> : null}
      <Field label="Reason (optional)" testID="roster-reason" value={reason} onChangeText={setReason} placeholder="e.g. Tactical move" />
      {!dateOk || !loanOk ? <Notice kind="warn" text={!dateOk ? 'Enter the date as YYYY-MM-DD.' : 'The loan end date must be after the start date.'} /> : null}

      {result ? <Notice kind={result.kind === 'sent' ? 'ok' : result.kind === 'queued' ? 'info' : 'error'} text={result.text} testID="roster-result" /> : null}
      <HexButton testID="roster-submit" kind={kind === 'release' ? 'danger' : 'accent'} icon={kind === 'release' ? 'exit-outline' : 'swap-horizontal'}
        label={!player ? 'Choose a player' : kind === 'release' ? 'Release player' : `Confirm ${kind}`} disabled={!ready} loading={busy} onPress={confirm} style={{ marginTop: 12 }} />
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 12 }}>
        <Ionicons name="cloud-offline-outline" size={16} color={palette.ink3} />
        <T kind="muted" style={{ flex: 1 }}>Works offline — the action is saved on this phone and synced later.</T>
      </View>
    </ScrollView>
  );
}
