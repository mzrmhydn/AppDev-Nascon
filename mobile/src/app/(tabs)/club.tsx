// Club tab: chips for every club of the tenant (GET /api/v1/clubs, cached), own club pre-selected for manager/player.
import { useEffect, useState } from 'react';
import { ScrollView, View } from 'react-native';
import * as api from '../../lib/api';
import { useSession } from '../../lib/session';
import { useCached } from '../../lib/useCached';
import { ClubProfile } from '../../ui/ClubProfile';
import { Chip, Empty, ErrorState, Loading, styles, T } from '../../ui/kit';

export default function ClubTab() {
  const { user } = useSession();
  const res = useCached('clubs', api.listClubs, [user?.user_id]);
  const clubs = res.data?.clubs ?? [];
  const [sel, setSel] = useState<string | null>(user?.club_id ?? null);
  useEffect(() => { if (!sel && clubs.length) setSel(clubs[0].club_id); }, [clubs, sel]);

  if (!res.data && res.loading) return <Loading label="Loading clubs…" />;
  if (!res.data) return <ErrorState message={res.error ?? ''} onRetry={res.reload} testID="clubs-retry" />;
  if (!clubs.length) return <Empty icon="shield-outline" title="No clubs yet" />;

  const header = (
    <View style={{ paddingTop: 16 }}>
      <T kind="display" style={[styles.pad, { fontSize: 34 }]} accessibilityRole="header">CLUBS</T>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, padding: 16 }}>
        {clubs.map((c) => (
          <Chip key={c.club_id} testID={`club-chip-${c.club_id}`} label={c.short_name || c.name} sub={c.club_id === user?.club_id ? 'My club' : c.name}
            selected={c.club_id === sel} onPress={() => setSel(c.club_id)} />
        ))}
      </ScrollView>
    </View>
  );
  return sel ? <ClubProfile key={sel} clubId={sel} header={header} /> : header;
}
