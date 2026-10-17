// League header shared by Fixtures and Standings: Bebas page title + red "LEAGUE ▾" tag that opens a picker.
// Loads GET /api/v1/leagues (cached) and remembers the choice.
import { useEffect, useState } from 'react';
import { Modal, Pressable, ScrollView, View } from 'react-native';
import * as api from '../lib/api';
import { useSession } from '../lib/session';
import { chooseLeague, setLeagues, useLeague } from '../lib/stores';
import { palette, TAP } from '../lib/theme';
import { useCached } from '../lib/useCached';
import { CachedNotice, Chip, HexButton, Tag, T } from './kit';

export function useLeagues() {
  const { user } = useSession();
  const res = useCached('leagues', api.listLeagues, [user?.user_id]);
  useEffect(() => { if (res.data) setLeagues(res.data.leagues, user?.league_id ?? null); }, [res.data, user?.league_id]);
  return res;
}

export function LeagueHeader({ title, testID }: { title: string; testID: string }) {
  const res = useLeagues();
  const { leagueId, leagues } = useLeague();
  const [open, setOpen] = useState(false);
  const current = leagues.find((l) => l.league_id === leagueId);
  const sport = (current?.sport_id ?? 'league').toUpperCase();

  return (
    <View style={{ paddingHorizontal: 16, paddingTop: 16 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <T kind="display" accessibilityRole="header" style={{ fontSize: 34 }}>{title}</T>
        {leagues.length ? <Tag testID={`${testID}-league-picker`} label={sport} a11y={`League: ${current?.name ?? 'none'}. Tap to change league`} onPress={() => setOpen(true)} /> : null}
      </View>
      {current ? <T kind="small" numberOfLines={1}>{current.name} · Season {current.season}</T> : null}
      <CachedNotice savedAt={res.fromCache} />

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={{ flex: 1, backgroundColor: 'rgba(21,0,0,0.5)', justifyContent: 'flex-end' }} onPress={() => setOpen(false)} accessibilityLabel="Close league picker">
          <Pressable style={{ backgroundColor: palette.page, padding: 16, maxHeight: '70%' }}>
            <T kind="display" style={{ fontSize: 26, marginBottom: 8 }}>CHOOSE A LEAGUE</T>
            <ScrollView contentContainerStyle={{ gap: 8 }}>
              {leagues.map((l) => (
                <Chip key={l.league_id} testID={`${testID}-league-${l.league_id}`} label={l.name} sub={`${(l.sport_id ?? 'no sport yet')} · ${l.season}`}
                  selected={l.league_id === leagueId} onPress={() => { chooseLeague(l.league_id); setOpen(false); }} />
              ))}
            </ScrollView>
            <HexButton testID={`${testID}-league-close`} kind="secondary" label="Close" onPress={() => setOpen(false)} style={{ marginTop: 12, minHeight: TAP }} />
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}
