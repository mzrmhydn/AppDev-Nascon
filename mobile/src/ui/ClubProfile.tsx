// Club profile (spec §8.2): info, home venue, socials, staff, season stats, roster. GET /api/v1/clubs/{id} (cached).
// Used by the Club tab (own club / club list) and the club/[id] route.
import { Ionicons } from '@expo/vector-icons';
import { RefreshControl, ScrollView, Text, View } from 'react-native';
import * as api from '../lib/api';
import { font, onColor, palette } from '../lib/theme';
import { useCached } from '../lib/useCached';
import { CachedNotice, Crest, Empty, ErrorState, Loading, SectionTitle, styles, T } from './kit';

const ROLE: Record<string, string> = { captain: 'Captain', vice_captain: 'Vice-captain', starter: 'Starter', substitute: 'Substitute' };
const REG: Record<string, string> = { initial: 'Registered', transfer: 'Transferred in', loan: 'On loan' };

export function ClubProfile({ clubId, header }: { clubId: string; header?: React.ReactNode }) {
  const res = useCached(`club:${clubId}`, () => api.getClub(clubId), [clubId]);
  const c = res.data;
  if (!c && res.loading) return <Loading label="Loading club…" />;
  if (!c) return <ErrorState message={res.error ?? 'Club not found.'} onRetry={res.reload} testID="club-retry" />;
  const color = /^#[0-9a-fA-F]{6}$/.test(c.primary_color) ? c.primary_color : palette.ink;

  return (
    <ScrollView style={styles.page} contentContainerStyle={{ paddingBottom: 32 }} refreshControl={<RefreshControl refreshing={false} onRefresh={res.reload} />}>
      {header}
      <View style={{ backgroundColor: color, padding: 16, flexDirection: 'row', alignItems: 'center', gap: 12 }}>
        <Crest id={c.club_id} name={c.name} color={color} big />
        <View style={{ flex: 1 }}>
          <Text accessibilityRole="header" style={{ fontFamily: font.display, fontSize: 32, color: onColor(color) }} numberOfLines={2}>{c.name.toUpperCase()}</Text>
          <Text style={{ fontFamily: font.medium, color: onColor(color), opacity: 0.9 }}>{c.short_name} · {c.roster.length} players</Text>
        </View>
      </View>
      <View style={styles.pad}>
        <CachedNotice savedAt={res.fromCache} />

        <SectionTitle>HOME VENUE</SectionTitle>
        {c.home_venue ? (
          <View style={[styles.card, { flexDirection: 'row', gap: 12, alignItems: 'center' }]} accessible accessibilityLabel={`Home venue ${c.home_venue.name}, ${c.home_venue.city}`}>
            <Ionicons name="location" size={24} color={palette.red} />
            <View><T kind="title">{c.home_venue.name}</T><T kind="muted">{c.home_venue.city} · {typeof c.home_venue.lat === "number" ? `${c.home_venue.lat.toFixed(4)}, ${c.home_venue.lng.toFixed(4)}` : ""}</T></View>
          </View>
        ) : <T kind="muted">No home venue listed.</T>}

        {(c.socials.instagram || c.socials.x || c.socials.facebook) ? (
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginBottom: 4 }}>
            {c.socials.instagram ? <Social icon="logo-instagram" label={`Instagram ${c.socials.instagram}`} text={c.socials.instagram} /> : null}
            {c.socials.x ? <Social icon="logo-twitter" label={`X ${c.socials.x}`} text={c.socials.x} /> : null}
            {c.socials.facebook ? <Social icon="logo-facebook" label={`Facebook ${c.socials.facebook}`} text={c.socials.facebook} /> : null}
          </View>
        ) : null}

        <SectionTitle>STAFF</SectionTitle>
        {c.staff.length === 0 ? <T kind="muted">No staff listed yet.</T> : c.staff.map((s, i) => (
          <View key={i} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8 }} accessible accessibilityLabel={`${s.name}, ${s.role}`}>
            <Ionicons name={s.role === 'coach' ? 'clipboard-outline' : s.role === 'physio' ? 'medkit-outline' : 'briefcase-outline'} size={20} color={palette.ink2} />
            <T style={{ flex: 1 }}>{s.name}</T><T kind="label">{s.role}</T>
          </View>
        ))}

        {c.stats.length ? (
          <>
            <SectionTitle>SEASON RECORD</SectionTitle>
            {c.stats.map((s) => (
              <View key={s.season} style={[styles.card, { flexDirection: 'row', justifyContent: 'space-between' }]} accessible accessibilityLabel={`Season ${s.season}: played ${s.played}, won ${s.won}, drawn ${s.drawn}, lost ${s.lost}, trophies ${s.trophies}`}>
                <Text style={{ fontFamily: font.display, fontSize: 22 }}>{s.season}</Text>
                {[['P', s.played], ['W', s.won], ['D', s.drawn], ['L', s.lost], ['🏆', s.trophies]].map(([k, v]) => (
                  <View key={String(k)} style={{ alignItems: 'center' }}><T kind="label">{k}</T><T kind="title">{v}</T></View>
                ))}
              </View>
            ))}
          </>
        ) : null}

        <SectionTitle>{`ROSTER (${c.roster.length})`}</SectionTitle>
        {c.roster.length === 0 ? <Empty icon="people-outline" title="No players registered" /> : c.roster.map((p, i) => (
          <View key={p.player_id} testID={`roster-${p.player_id}`} accessible accessibilityLabel={`${p.name}, position ${p.position ?? "unknown"}, ${ROLE[p.role] ?? p.role}, ${REG[p.registration_type] ?? ''}`}
            style={{ flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 52, paddingHorizontal: 8, backgroundColor: i % 2 ? 'transparent' : palette.surface }}>
            <Text style={{ fontFamily: font.display, fontSize: 18, width: 36, color: palette.ink3 }}>{(p.position ?? "–").toUpperCase()}</Text>
            <View style={{ flex: 1 }}>
              <T numberOfLines={1}>{p.name}</T>
              <T kind="muted">{ROLE[p.role] ?? p.role}{p.registration_type === 'loan' ? ' · On loan' : ''}</T>
            </View>
            {p.role === 'captain' ? <View accessibilityElementsHidden style={{ backgroundColor: palette.ink, paddingHorizontal: 6, paddingVertical: 2 }}><Text style={{ color: '#fff', fontFamily: font.display }}>C</Text></View> : null}
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

function Social({ icon, label, text }: { icon: keyof typeof Ionicons.glyphMap; label: string; text: string }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 8 }} accessible accessibilityLabel={label}>
      <Ionicons name={icon} size={18} color={palette.ink2} /><T kind="small">{text}</T>
    </View>
  );
}
