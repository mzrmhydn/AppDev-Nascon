// Fixtures (spec §8.2): Upcoming / Live / Past tabs, Sportify match cards with status + time; tap → Match detail.
// Data: GET /api/v1/leagues/{id}/fixtures, cached in SQLite for offline use (NFR-4).
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useMemo, useState } from 'react';
import { FlatList, Pressable, RefreshControl, Text, View } from 'react-native';
import * as api from '../../lib/api';
import { useLeague } from '../../lib/stores';
import { font, palette, when } from '../../lib/theme';
import type { Fixture } from '../../lib/types';
import { useCached } from '../../lib/useCached';
import { StatusPill } from '../../ui/StatusPill';
import { CachedNotice, Crest, Empty, ErrorState, Loading, styles, Tabs, T } from '../../ui/kit';
import { LeagueHeader } from '../../ui/LeagueHeader';
import { Appear } from '../../ui/Appear';

type Tab = 'upcoming' | 'live' | 'past';
const STATUS_TEXT = { upcoming: 'Upcoming', in_progress: 'Live', completed: 'Full time' } as const;

function MatchCard({ f, index }: { f: Fixture; index: number }) {
  const score = f.home_score === null ? 'vs' : `${f.home_score} - ${f.away_score}`;
  const a11y = `${f.home.name} ${f.home_score ?? ''} versus ${f.away.name} ${f.away_score ?? ''}. ${STATUS_TEXT[f.status]}. ${when(f.scheduled_at)}. ${f.venue ?? ''}. Open match`;
  return (
    <Appear delay={Math.min(index, 6) * 40}>
      <Pressable testID={`fixture-${f.match_id}`} accessibilityRole="button" accessibilityLabel={a11y}
        onPress={() => router.push({ pathname: '/match/[id]', params: { id: f.match_id } })}
        style={({ pressed }) => ({ marginBottom: 16, opacity: pressed ? 0.85 : 1 })}>
        <View style={{ backgroundColor: palette.gray10, overflow: 'hidden', padding: 16 }}>
          {/* diagonal lighter half from the Figma card */}
          <View style={{ position: 'absolute', top: -40, bottom: -40, right: -60, width: '55%', backgroundColor: '#E2E1E1', transform: [{ skewX: '-12deg' }] }} />
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <StatusPill status={f.status} />
            <Text style={{ fontFamily: font.medium, fontSize: 13, color: palette.ink2, backgroundColor: palette.gray20, paddingHorizontal: 8, paddingVertical: 4 }}>{when(f.scheduled_at)}</Text>
          </View>
          <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 16, gap: 8 }}>
            <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Crest id={f.home.team_id} name={f.home.name} />
              <Text style={{ flex: 1, fontFamily: font.semibold, fontSize: 15, color: palette.ink, textTransform: 'uppercase' }} numberOfLines={2}>{f.home.name}</Text>
            </View>
            <Text style={{ fontFamily: font.display, fontSize: 32, color: palette.ink, minWidth: 64, textAlign: 'center' }}>{score}</Text>
            <View style={{ flex: 1, flexDirection: 'row-reverse', alignItems: 'center', gap: 8 }}>
              <Crest id={f.away.team_id} name={f.away.name} />
              <Text style={{ flex: 1, fontFamily: font.semibold, fontSize: 15, color: palette.ink, textTransform: 'uppercase', textAlign: 'right' }} numberOfLines={2}>{f.away.name}</Text>
            </View>
          </View>
        </View>
        <View style={{ backgroundColor: palette.ink2, paddingHorizontal: 16, paddingVertical: 10, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
          <View>
            <Text style={{ fontFamily: font.semibold, fontSize: 14, color: '#fff' }}>{f.round ? `ROUND ${f.round}` : 'MATCH'}</Text>
            <Text style={{ fontFamily: font.regular, fontSize: 12, color: palette.gray20 }} numberOfLines={1}>{f.venue ?? 'Venue to be confirmed'}</Text>
          </View>
          <Ionicons name="chevron-forward" size={20} color="#fff" />
        </View>
      </Pressable>
    </Appear>
  );
}

export default function Fixtures() {
  const { leagueId } = useLeague();
  const [tab, setTab] = useState<Tab>('upcoming');
  const res = useCached(leagueId ? `fixtures:${leagueId}` : null, () => api.listFixtures(leagueId!), [leagueId]);
  const all = res.data?.fixtures ?? [];
  const counts = { upcoming: all.filter((f) => f.status === 'upcoming').length, live: all.filter((f) => f.status === 'in_progress').length, past: all.filter((f) => f.status === 'completed').length };
  const list = useMemo(() => all.filter((f) => (tab === 'upcoming' ? f.status === 'upcoming' : tab === 'live' ? f.status === 'in_progress' : f.status === 'completed')), [all, tab]);

  let body;
  if (!leagueId) body = <Empty icon="trophy-outline" title="No leagues yet" hint="When a league is set up for your organisation it will appear here." />;
  else if (res.loading && !res.data) body = <Loading label="Loading matches…" />;
  else if (res.error && !res.data) body = <ErrorState message={res.error} onRetry={res.reload} testID="fixtures-retry" />;

  return (
    <View style={styles.page}>
      <FlatList
        data={body ? [] : list}
        keyExtractor={(f) => f.match_id}
        renderItem={({ item, index }) => <View style={styles.pad}><MatchCard f={item} index={index} /></View>}
        refreshControl={<RefreshControl refreshing={res.loading && !!res.data} onRefresh={res.reload} />}
        ListHeaderComponent={
          <>
            <LeagueHeader title="MATCHES" testID="fixtures" />
            <View style={[styles.pad, { marginTop: 8, marginBottom: 12 }]}>
              <Tabs testID="fixtures-tab" value={tab} onChange={setTab} tabs={[
                { key: 'upcoming', label: `Upcoming (${counts.upcoming})` }, { key: 'live', label: `Live (${counts.live})` }, { key: 'past', label: `Past (${counts.past})` },
              ]} />
            </View>
            {res.data && res.fromCache === null ? null : <View style={styles.pad}><CachedNotice savedAt={res.fromCache} /></View>}
          </>
        }
        ListEmptyComponent={body ?? <Empty icon="calendar-outline" title={tab === 'live' ? 'No live matches right now' : tab === 'past' ? 'No finished matches yet' : 'No upcoming matches'} hint="Pull down to refresh." />}
        contentContainerStyle={{ paddingBottom: 24 }}
      />
    </View>
  );
}
