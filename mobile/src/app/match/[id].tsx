// Match detail (spec §8.2): live score (WebSocket /ws/matches/{id} + 5 s polling fallback), event timeline with
// compensated events struck through and labelled, pinned product showcase. Contract §1 / §2.8 / §2.14.
import { Ionicons } from '@expo/vector-icons';
import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';
import * as api from '../../lib/api';
import { wsUrl, getMock } from '../../lib/config';
import { cacheGet } from '../../lib/db';
import { font, money, palette, TAP } from '../../lib/theme';
import type { Fixture, FixturesResponse, MatchEvent, Score } from '../../lib/types';
import { useCached } from '../../lib/useCached';
import { useLeague } from '../../lib/stores';
import { CachedNotice, Crest, Empty, ErrorState, HexButton, Loading, styles, Tabs, T } from '../../ui/kit';
import { StatusPill } from '../../ui/StatusPill';
import { Appear } from '../../ui/Appear';

const humanize = (s: string) => s.replace(/[_-]+/g, ' ').replace(/^\w/, (c) => c.toUpperCase());

/** Team names come from the cached fixtures list (score only has ids). */
function useTeamNames(matchId: string) {
  const { leagueId } = useLeague();
  const fx = leagueId ? cacheGet<FixturesResponse>(`fixtures:${leagueId}`)?.data : null;
  const f: Fixture | undefined = fx?.fixtures.find((x) => x.match_id === matchId);
  return { f, name: (id: string) => (f?.home.team_id === id ? f.home.name : f?.away.team_id === id ? f.away.name : id) };
}

function describe(e: MatchEvent, name: (id: string) => string, all: MatchEvent[]): { icon: keyof typeof Ionicons.glyphMap; text: string } {
  const p = e.payload ?? {};
  switch (e.type) {
    case 'match_init': return { icon: 'create-outline', text: 'Match created' };
    case 'match_start': return { icon: 'play-circle-outline', text: 'Kick-off — match started' };
    case 'match_end': return { icon: 'flag-outline', text: 'Full time — match ended' };
    case 'score': return { icon: 'add-circle-outline', text: `${humanize(String(p.event_type ?? 'Score'))} — ${name(p.team_id)}` };
    case 'discipline': return { icon: 'warning-outline', text: `Discipline ${p.points > 0 ? '+' : ''}${p.points} fair-play — ${name(p.team_id)}` };
    case 'tiebreak_winner': return { icon: 'trophy-outline', text: `Tie-break won by ${name(p.team_id)}` };
    case 'compensation': {
      const t = all.find((x) => x.event_id === p.compensates);
      return { icon: 'arrow-undo-outline', text: `Correction: event #${t?.sequence ?? '?'} cancelled${p.reason ? ` — “${p.reason}”` : ''}` };
    }
    default: return { icon: 'ellipse-outline', text: humanize(e.type) };
  }
}

const OUTCOME: Record<Score['outcome'], string> = { pending: '', home_win: 'Home win', away_win: 'Away win', draw: 'Draw', undecided: 'Result undecided' };

export default function MatchDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { f, name } = useTeamNames(id);
  const [tab, setTab] = useState<'timeline' | 'shop'>('timeline');
  const score = useCached(`score:${id}`, () => api.getScore(id), [id]);
  const show = useCached(`showcase:${id}`, () => api.getShowcase(id), [id]);
  const [live, setLive] = useState(false);
  const [bump, setBump] = useState(0);

  // Live updates: WebSocket messages trigger a re-fetch; polling every 5 s covers a dropped socket.
  useEffect(() => {
    const poll = setInterval(() => score.reload(), 5000);
    let ws: WebSocket | null = null;
    if (!getMock()) {
      try {
        ws = new WebSocket(wsUrl(`/ws/matches/${encodeURIComponent(id)}`));
        ws.onopen = () => setLive(true);
        ws.onclose = () => setLive(false);
        ws.onerror = () => setLive(false);
        ws.onmessage = (m) => {
          try {
            const msg = JSON.parse(String(m.data));
            if (msg.type === 'match_updated') { score.reload(); setBump((b) => b + 1); }
            if (msg.type === 'showcase_updated') show.reload();
          } catch { /* ignore non-JSON */ }
        };
      } catch { setLive(false); }
    }
    return () => { clearInterval(poll); ws?.close(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const s = score.data;
  if (!s && score.loading) return <Loading label="Loading match…" />;
  if (!s) return <ErrorState message={score.error ?? 'Match not found.'} onRetry={score.reload} testID="match-retry" />;

  const homeName = f?.home.name ?? s.home.team_id, awayName = f?.away.name ?? s.away.team_id;
  const side = (x: Score['home']) => (x.overs !== null ? `${x.score}/${x.wickets ?? 0}` : String(x.score));
  const product = show.data?.product;

  return (
    <ScrollView style={styles.page} contentContainerStyle={{ paddingBottom: 32 }}
      refreshControl={<RefreshControl refreshing={false} onRefresh={() => { score.reload(); show.reload(); }} />}>
      <Stack.Screen options={{ title: f?.round ? `ROUND ${f.round}` : 'MATCH' }} />
      <View style={[styles.pad, { paddingTop: 4 }]}>
        <CachedNotice savedAt={score.fromCache} />
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <StatusPill status={s.status} />
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }} accessibilityLabel={live ? 'Live updates connected' : 'Updating every 5 seconds'}>
            <Ionicons name={live ? 'flash' : 'refresh'} size={14} color={palette.ink3} />
            <T kind="muted">{live ? 'Live updates on' : 'Updates every 5 s'}</T>
          </View>
        </View>
        <T kind="muted" style={{ marginTop: 4 }}>{f?.venue ?? ''}</T>

        {/* Scoreboard — the most important thing on the screen */}
        <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 16 }} accessible accessibilityLabel={`Score: ${homeName} ${side(s.home)}, ${awayName} ${side(s.away)}. ${OUTCOME[s.outcome]}`}>
          <View style={{ flex: 1, alignItems: 'center', gap: 6 }}>
            <Crest id={s.home.team_id} name={homeName} big />
            <Text style={{ fontFamily: font.semibold, fontSize: 14, textAlign: 'center', textTransform: 'uppercase', color: palette.ink }} numberOfLines={2}>{homeName}</Text>
          </View>
          <View style={{ alignItems: 'center', minWidth: 120 }}>
            <Appear kind="zoom" key={`${s.version}-${bump}`}>
                <Text style={{ fontFamily: font.display, fontSize: 56, color: palette.ink }}>{side(s.home)} - {side(s.away)}</Text>
              </Appear>
            {s.home.overs !== null ? <T kind="muted">{s.home.overs} ov · {s.away.overs} ov</T> : null}
            <T kind="small">{s.status === 'completed' ? OUTCOME[s.outcome] || 'Full time' : s.status === 'in_progress' ? 'In progress' : 'Not started'}</T>
          </View>
          <View style={{ flex: 1, alignItems: 'center', gap: 6 }}>
            <Crest id={s.away.team_id} name={awayName} big />
            <Text style={{ fontFamily: font.semibold, fontSize: 14, textAlign: 'center', textTransform: 'uppercase', color: palette.ink }} numberOfLines={2}>{awayName}</Text>
          </View>
        </View>

        <View style={{ marginTop: 16 }}>
          <Tabs testID="match-tab" value={tab} onChange={setTab} tabs={[{ key: 'timeline', label: `Timeline (${s.events.length})` }, { key: 'shop', label: product ? 'Pinned product' : 'Shop' }]} />
        </View>

        {tab === 'timeline' ? (
          s.events.length === 0 ? <Empty icon="list-outline" title="No events yet" hint="Events appear here as soon as they are recorded." /> : (
            <View style={{ marginTop: 8 }}>
              {[...s.events].reverse().map((e) => {
                const d = describe(e, name, s.events);
                return (
                  <View key={e.event_id} testID={`event-${e.event_id}`} accessible
                    accessibilityLabel={`Event ${e.sequence}. ${d.text}.${e.compensated ? ' Cancelled by a correction.' : ''}`}
                    style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: palette.gray10, backgroundColor: e.compensated ? palette.gray10 : 'transparent', paddingHorizontal: 8 }}>
                    <Text style={{ fontFamily: font.display, fontSize: 18, color: palette.ink3, width: 28 }}>#{e.sequence}</Text>
                    <Ionicons name={d.icon} size={20} color={e.compensated ? palette.ink4 : palette.ink} />
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontFamily: font.medium, fontSize: 15, color: e.compensated ? palette.ink3 : palette.ink, textDecorationLine: e.compensated ? 'line-through' : 'none' }}>{d.text}</Text>
                      {e.compensated ? <Text style={{ fontFamily: font.semibold, fontSize: 12, color: palette.redDark }}>CANCELLED — does not count</Text> : null}
                    </View>
                  </View>
                );
              })}
            </View>
          )
        ) : product ? (
          <View style={[styles.card, { marginTop: 12 }]}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <Ionicons name="pin" size={16} color={palette.red} />
              <T kind="label">Pinned for this match</T>
            </View>
            <T kind="display" style={{ fontSize: 26 }}>{product.name.toUpperCase()}</T>
            <T kind="muted" style={{ marginBottom: 8 }}>{product.description}</T>
            <T kind="title" style={{ marginBottom: 12 }}>from {money(Math.min(...product.variants.map((v) => v.price_minor)))}</T>
            <HexButton testID="match-showcase-buy" kind="accent" icon="bag-add-outline" label="Buy now" onPress={() => router.push({ pathname: '/product/[id]', params: { id: product.product_id } })} />
          </View>
        ) : (
          <Empty icon="bag-outline" title="No product pinned for this match" hint="Browse the club store from the Store tab." />
        )}
      </View>
    </ScrollView>
  );
}
