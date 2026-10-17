// "Me" tab (spec §8.6 "Profile"): who is signed in, role, tenant, quick links to Sync status and Settings.
import { router } from 'expo-router';
import { Alert, ScrollView, Text, View } from 'react-native';
import { signOut, useSession } from '../../lib/session';
import { useSync } from '../../lib/sync';
import { font, onColor, useAccent } from '../../lib/theme';
import { HexButton, SectionTitle, styles, T } from '../../ui/kit';

const ROLE: Record<string, string> = { super_admin: 'Platform Super-Admin', league_organizer: 'League Organizer', club_manager: 'Club Manager', player: 'Player', viewer: 'General Viewer' };

export default function Me() {
  const { user, tenant } = useSession();
  const { pending } = useSync();
  const { accent } = useAccent();
  if (!user) return null;
  return (
    <ScrollView style={styles.page} contentContainerStyle={{ paddingBottom: 40 }}>
      <View style={{ backgroundColor: accent, padding: 16, paddingTop: 24 }}>
        <Text style={{ fontFamily: font.display, fontSize: 16, color: onColor(accent), opacity: 0.85 }}>{(tenant?.name ?? 'NaSCon Platform').toUpperCase()}</Text>
        <Text accessibilityRole="header" style={{ fontFamily: font.display, fontSize: 38, color: onColor(accent) }}>{user.display_name.toUpperCase()}</Text>
        <Text style={{ fontFamily: font.medium, color: onColor(accent) }}>{ROLE[user.role]} · {user.email}</Text>
      </View>
      <View style={styles.pad}>
        <SectionTitle>MY ACCESS</SectionTitle>
        {user.league_id ? <T>League: {user.league_id}</T> : null}
        {user.club_id ? <T>Club: {user.club_id}</T> : null}
        {user.player_id ? <T>Player: {user.player_id}</T> : null}
        {!user.league_id && !user.club_id ? <T kind="muted">{user.role === 'super_admin' ? 'All organisations.' : 'Read-only access to your organisation.'}</T> : null}
        <View style={{ gap: 12, marginTop: 20 }}>
          <HexButton testID="me-sync" icon="sync" label={`Sync status (${pending.length} pending)`} onPress={() => router.push('/sync')} />
          <HexButton testID="me-settings" kind="secondary" icon="settings-outline" label="Settings" onPress={() => router.push('/settings')} />
          <HexButton testID="me-signout" kind="danger" icon="log-out-outline" label="Sign out"
            onPress={() => Alert.alert('Sign out?', pending.length ? `${pending.length} pending action(s) stay saved on this phone.` : 'You can sign in again any time.', [
              { text: 'Cancel', style: 'cancel' }, { text: 'Sign out', style: 'destructive', onPress: async () => { await signOut(); router.replace('/login'); } }])} />
        </View>
      </View>
    </ScrollView>
  );
}
