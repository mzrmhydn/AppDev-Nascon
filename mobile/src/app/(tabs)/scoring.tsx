// Scoring entry for League Organizer (spec §8.2): start / score / discipline / end a match and append a compensating
// event, via POST /api/v1/events (body = spec §5.9). Offline → queued as score_event with base_version = score.version.
// Event types are never hard-coded: they come from the match logs (see CONTRACT REQUEST in notes) + free text.
import { Ionicons } from '@expo/vector-icons';
import { useEffect, useMemo, useState } from 'react';
import { Alert, ScrollView, Text, View } from 'react-native';
import * as api from '../../lib/api';
import { cacheGet, cacheSet, newId } from '../../lib/db';
import { useSession } from '../../lib/session';
import { useLeague } from '../../lib/stores';
import { font, palette } from '../../lib/theme';
import type { EventRequest, Fixture, Score } from '../../lib/types';
import { useCached } from '../../lib/useCached';
import { sendOrQueue, SendResult } from '../../lib/writes';
import { CachedNotice, Chip, Empty, ErrorState, Field, HexButton, Loading, Notice, SectionTitle, styles, T } from '../../ui/kit';
import { useLeagues } from '../../ui/LeagueHeader';

const humanize = (s: string) => s.replace(/[_-]+/g, ' ').replace(/^\w/, (c) => c.toUpperCase());

export default function Scoring() {
  const { user } = useSession();
  useLeagues();
  const { leagueId: chosen } = useLeague();
  const leagueId = user?.role === 'league_organizer' ? user.league_id : chosen;
  const fx = useCached(leagueId ? `fixtures:${leagueId}` : null, () => api.listFixtures(leagueId!), [leagueId]);
  const [matchId, setMatchId] = useState<string | null>(null);
  const score = useCached(matchId ? `score:${matchId}` : null, () => (matchId ? api.getScore(matchId) : Promise.reject()), [matchId]);
  const [team, setTeam] = useState<string | null>(null);
  const [eventType, setEventType] = useState<string>('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SendResult | null>(null);

  const fixtures = fx.data?.fixtures ?? [];
  const match: Fixture | undefined = fixtures.find((f) => f.match_id === matchId);
  const s: Score | null = score.data;
  useEffect(() => { setTeam(null); setResult(null); }, [matchId]);

  // Event types seen in any cached match of this league (sport config route is not in the contract yet).
  const knownTypes = useMemo(() => {
    const set = new Set<string>();
    for (const f of fixtures) for (const e of cacheGet<Score>(`score:${f.match_id}`)?.data.events ?? []) if (e.type === 'score' && e.payload?.event_type) set.add(String(e.payload.event_type));
    for (const e of s?.events ?? []) if (e.type === 'score' && e.payload?.event_type) set.add(String(e.payload.event_type));
    return [...set];
  }, [fixtures, s]);
  useEffect(() => { if (!eventType && knownTypes.length) setEventType(knownTypes[0]); }, [knownTypes, eventType]);

  if (!leagueId) return <Empty icon="stopwatch-outline" title="No league linked to your account" />;
  if (!fx.data && fx.loading) return <Loading label="Loading matches…" />;
  if (!fx.data) return <ErrorState message={fx.error ?? ''} onRetry={fx.reload} testID="scoring-retry" />;

  const teamName = (id: string) => (match?.home.team_id === id ? match.home.name : match?.away.team_id === id ? match.away.name : id);
  const status = s?.status ?? match?.status;
  const active = (s?.events ?? []).filter((e) => !e.compensated && ['score', 'discipline', 'tiebreak_winner'].includes(e.type));

  async function send(type: string, payload: Record<string, any>, label: string) {
    if (!matchId) return;
    const body: EventRequest = { event_id: newId('evt'), match_id: matchId, type, payload };
    setBusy(true); setResult(null);
    const r = await sendOrQueue('score_event', s?.version ?? match?.version ?? 0, body, `${label} (${match?.home.name} v ${match?.away.name})`);
    setResult(r.kind === 'sent' ? { ...r, text: `Recorded: ${label}.` } : r);
    setBusy(false);
    if (r.kind === 'sent') { const fresh = await api.getScore(matchId).catch(() => null); if (fresh) cacheSet(`score:${matchId}`, fresh); score.reload(); }
  }
  const ask = (title: string, text: string, go: () => void, destructive = false) =>
    Alert.alert(title, text, [{ text: 'Cancel', style: 'cancel' }, { text: 'Confirm', style: destructive ? 'destructive' : 'default', onPress: go }]);

  return (
    <ScrollView style={styles.page} contentContainerStyle={{ padding: 16, paddingBottom: 40 }} keyboardShouldPersistTaps="handled">
      <T kind="display" accessibilityRole="header" style={{ fontSize: 34 }}>SCORING</T>
      <CachedNotice savedAt={fx.fromCache} />

      <SectionTitle>1. MATCH</SectionTitle>
      {fixtures.length === 0 ? <T kind="muted">No matches in this league yet.</T> : (
        <View style={{ gap: 8 }}>
          {fixtures.map((f) => <Chip key={f.match_id} testID={`scoring-match-${f.match_id}`} label={`${f.home.name} v ${f.away.name}`} sub={`${f.status === 'in_progress' ? 'Live' : f.status === 'completed' ? 'Finished' : 'Upcoming'}${f.home_score !== null ? ` · ${f.home_score}-${f.away_score}` : ''}`} selected={f.match_id === matchId} onPress={() => setMatchId(f.match_id)} />)}
        </View>
      )}

      {match ? (
        <>
          <View style={[styles.card, { marginTop: 16, alignItems: 'center' }]} accessible accessibilityLabel={`Current score ${match.home.name} ${s?.home.score ?? '-'}, ${match.away.name} ${s?.away.score ?? '-'}`}>
            <T kind="label">{status === 'in_progress' ? 'Live' : status === 'completed' ? 'Finished' : 'Not started'} · version {s?.version ?? match.version}</T>
            <Text style={{ fontFamily: font.display, fontSize: 44 }}>{s ? `${s.home.score} - ${s.away.score}` : '– -'}</Text>
            {score.fromCache ? <T kind="muted">Saved score — may be out of date while offline</T> : null}
          </View>

          {status === 'upcoming' ? (
            <HexButton testID="scoring-start" icon="play" label="Start match" loading={busy} onPress={() => ask('Start match?', `${match.home.name} v ${match.away.name} will be marked as live.`, () => send('match_start', {}, 'Match started'))} />
          ) : null}

          <SectionTitle>2. ADD SCORE</SectionTitle>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            {[match.home, match.away].map((t) => <View key={t.team_id} style={{ flex: 1 }}><Chip testID={`scoring-team-${t.team_id}`} label={t.name} selected={team === t.team_id} onPress={() => setTeam(t.team_id)} /></View>)}
          </View>
          {knownTypes.length ? (
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
              {knownTypes.map((t) => <Chip key={t} testID={`scoring-type-${t}`} label={humanize(t)} selected={eventType === t} onPress={() => setEventType(t)} />)}
            </View>
          ) : null}
          <Field label="Scoring event name (from the sport rules)" testID="scoring-event-type" value={eventType} onChangeText={(v) => setEventType(v.trim().toLowerCase().replace(/\s+/g, '_'))} autoCapitalize="none" placeholder="type the event name" />
          <HexButton testID="scoring-add" kind="accent" icon="add-circle" label="Add score event" loading={busy} disabled={!team || !eventType}
            onPress={() => send('score', { team_id: team, event_type: eventType }, `${humanize(eventType)} for ${teamName(team!)}`)} />
          {status !== 'in_progress' && status ? <T kind="muted" style={{ marginTop: 4 }}>Scores are accepted only while the match is live.</T> : null}

          <SectionTitle>3. CORRECT AN EVENT</SectionTitle>
          <Field label="Reason for the correction" testID="scoring-reason" value={reason} onChangeText={setReason} placeholder="e.g. Goal disallowed after review" />
          {active.length === 0 ? <T kind="muted">No events that can be corrected.</T> : [...active].reverse().map((e) => (
            <View key={e.event_id} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <T style={{ flex: 1 }} numberOfLines={2}>#{e.sequence} {e.type === 'score' ? humanize(String(e.payload.event_type)) : humanize(e.type)} — {teamName(e.payload.team_id)}</T>
              <HexButton testID={`scoring-compensate-${e.event_id}`} kind="secondary" icon="arrow-undo" label="Undo" style={{ width: 120 }} a11y={`Cancel event ${e.sequence}`}
                onPress={() => ask('Cancel this event?', `Event #${e.sequence} will stop counting. The original stays in the log, struck through.`, () => send('compensation', { compensates: e.event_id, reason: reason.trim() || 'Correction' }, `Correction of event #${e.sequence}`), true)} />
            </View>
          ))}

          {status === 'in_progress' ? (
            <>
              <SectionTitle>4. FINISH</SectionTitle>
              <HexButton testID="scoring-end" kind="danger" icon="flag" label="End match" loading={busy} onPress={() => ask('End match?', 'The result will count in the standings.', () => send('match_end', {}, 'Match ended'), true)} />
            </>
          ) : null}

          {result ? <Notice kind={result.kind === 'sent' ? 'ok' : result.kind === 'queued' ? 'info' : 'error'} text={result.text} testID="scoring-result" /> : null}
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 12 }}>
            <Ionicons name="cloud-offline-outline" size={16} color={palette.ink3} />
            <T kind="muted" style={{ flex: 1 }}>Works offline — events are saved on this phone and synced later.</T>
          </View>
        </>
      ) : null}
    </ScrollView>
  );
}
