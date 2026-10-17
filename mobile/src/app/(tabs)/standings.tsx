// Standings (spec §8.2): points table from GET /audit/v1/standings/{league_id} (cached for offline).
// Qualification status shown as icon + words ("Qualified", "Out", "In contention") — never colour alone.
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { FlatList, Pressable, RefreshControl, Text, View } from 'react-native';
import * as api from '../../lib/api';
import { useLeague } from '../../lib/stores';
import { font, palette } from '../../lib/theme';
import type { QualStatus, StandingRow } from '../../lib/types';
import { useCached } from '../../lib/useCached';
import { CachedNotice, Crest, Empty, ErrorState, Loading, styles, T } from '../../ui/kit';
import { LeagueHeader } from '../../ui/LeagueHeader';
import { Appear } from '../../ui/Appear';

const QUAL: Record<QualStatus, { icon: keyof typeof Ionicons.glyphMap; text: string; color: string }> = {
  clinched: { icon: 'checkmark-circle', text: 'Qualified', color: palette.live },
  still_possible: { icon: 'ellipse-outline', text: 'In contention', color: palette.ink3 },
  eliminated: { icon: 'close-circle', text: 'Out', color: palette.redDark },
};
const TIE: Record<string, string> = { h2h_points: 'head-to-head points', h2h_diff: 'head-to-head difference', overall_diff: 'overall difference', scored: 'scored', fair_play: 'fair play', draw_lots: 'drawing of lots' };

const COL = 34;
function Head() {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, height: 40, borderBottomWidth: 1, borderBottomColor: palette.gray20 }} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Text style={[h, { width: 26 }]}>#</Text>
      <Text style={[h, { flex: 1 }]}>TEAM</Text>
      {['P', 'W', 'D', 'L', 'GD'].map((c) => <Text key={c} style={[h, { width: COL, textAlign: 'center' }]}>{c}</Text>)}
      <Text style={[h, { width: 40, textAlign: 'center', color: palette.ink }]}>PTS</Text>
    </View>
  );
}
const h = { fontFamily: font.display, fontSize: 16, color: palette.ink3, letterSpacing: 0.5 } as const;

function Row({ r, name, i, spots }: { r: StandingRow; name: string; i: number; spots: number }) {
  const q = QUAL[r.status];
  const diff = Number.isInteger(r.diff) ? (r.diff > 0 ? `+${r.diff}` : String(r.diff)) : r.diff.toFixed(3);
  return (
    <Appear kind="fade" delay={i * 30}>
      <Pressable testID={`standings-row-${r.team_id}`} accessibilityRole="button"
        accessibilityLabel={`Rank ${r.rank}, ${name}. ${r.points} points. Played ${r.played}, won ${r.won}, drawn ${r.drawn}, lost ${r.lost}, difference ${diff}. ${q.text}. Open club`}
        onPress={() => router.push({ pathname: '/club/[id]', params: { id: r.team_id } })}
        style={({ pressed }) => ({ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, minHeight: 60, backgroundColor: pressed ? palette.dangerSoft : i % 2 === 0 ? palette.surface : palette.page, borderBottomWidth: i + 1 === spots ? 2 : 0, borderBottomColor: palette.red })}>
        <Text style={{ width: 26, fontFamily: font.display, fontSize: 20, color: palette.ink }}>{r.rank}</Text>
        <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <Crest id={r.team_id} name={name} />
          <View style={{ flex: 1 }}>
            <Text style={{ fontFamily: font.semibold, fontSize: 14, color: palette.ink }} numberOfLines={1}>{name}</Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 3 }}>
              <Ionicons name={q.icon} size={12} color={q.color} />
              <Text style={{ fontFamily: font.medium, fontSize: 11, color: palette.ink3 }} numberOfLines={1}>{q.text}{r.resolved_by ? ` · ahead on ${TIE[r.resolved_by] ?? r.resolved_by}` : ''}</Text>
            </View>
          </View>
        </View>
        {[r.played, r.won, r.drawn, r.lost].map((v, k) => <Text key={k} style={cell}>{v}</Text>)}
        <Text style={cell}>{diff}</Text>
        <Text style={{ width: 40, textAlign: 'center', fontFamily: font.display, fontSize: 22, color: palette.ink }}>{r.points}</Text>
      </Pressable>
    </Appear>
  );
}
const cell = { width: COL, textAlign: 'center', fontFamily: font.medium, fontSize: 13, color: palette.ink2 } as const;

export default function Standings() {
  const { leagueId, leagues } = useLeague();
  const res = useCached(leagueId ? `standings:${leagueId}` : null, () => api.getStandings(leagueId!), [leagueId]);
  const league = leagues.find((l) => l.league_id === leagueId);
  const name = (id: string) => league?.teams.find((t) => t.team_id === id)?.name ?? id;
  const table = res.data?.table ?? [];

  let body;
  if (!leagueId) body = <Empty icon="podium-outline" title="No leagues yet" />;
  else if (res.loading && !res.data) body = <Loading label="Loading standings…" />;
  else if (res.error && !res.data) body = <ErrorState message={res.error} onRetry={res.reload} testID="standings-retry" />;

  return (
    <View style={styles.page}>
      <FlatList
        data={body ? [] : table}
        keyExtractor={(r) => r.team_id}
        renderItem={({ item, index }) => <Row r={item} name={name(item.team_id)} i={index} spots={res.data?.qualification_spots ?? 0} />}
        refreshControl={<RefreshControl refreshing={res.loading && !!res.data} onRefresh={res.reload} />}
        ListHeaderComponent={
          <>
            <LeagueHeader title="STANDINGS" testID="standings" />
            <View style={styles.pad}><CachedNotice savedAt={res.fromCache} /></View>
            {res.data ? <T kind="muted" style={{ paddingHorizontal: 16, marginVertical: 8 }}>Top {res.data.qualification_spots} qualify (red line). Tap a team to see the club.</T> : null}
            {body ? null : <Head />}
          </>
        }
        ListEmptyComponent={body ?? <Empty icon="podium-outline" title="No teams in this table yet" />}
        ListFooterComponent={table.length ? (
          <View style={{ padding: 16, gap: 6 }} accessibilityLabel="Legend">
            {Object.values(QUAL).map((q) => (
              <View key={q.text} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <Ionicons name={q.icon} size={16} color={q.color} /><T kind="small">{q.text}</T>
              </View>
            ))}
            <T kind="muted">P played · W won · D drawn · L lost · GD difference · PTS points</T>
          </View>
        ) : undefined}
        contentContainerStyle={{ paddingBottom: 24 }}
      />
    </View>
  );
}
