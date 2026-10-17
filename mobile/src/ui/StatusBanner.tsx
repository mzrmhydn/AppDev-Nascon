// Always-visible Online / Offline / Syncing bar with pending-action count (spec §8.2 "Sync status", §8.4).
// Icon + text for each state (never colour alone). Tap → Sync screen with the queue and results.
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { Pressable, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { getMock } from '../lib/config';
import { useSync } from '../lib/sync';
import { font, palette } from '../lib/theme';

export function StatusBanner() {
  const { mode, pending } = useSync();
  const insets = useSafeAreaInsets();
  const n = pending.length;
  const cfg = {
    online: { icon: 'cloud-done', text: 'Online', bg: palette.ink, fg: '#fff' },
    offline: { icon: 'cloud-offline', text: 'Offline — changes are saved on this phone', bg: palette.warn, fg: palette.ink },
    syncing: { icon: 'sync', text: 'Syncing…', bg: palette.live, fg: '#fff' },
  }[mode] as { icon: keyof typeof Ionicons.glyphMap; text: string; bg: string; fg: string };
  const label = `${cfg.text}${getMock() ? ' (sample data)' : ''}. ${n} pending ${n === 1 ? 'action' : 'actions'}. Tap to open sync status.`;
  return (
    <Pressable testID="status-banner" accessibilityRole="button" accessibilityLabel={label} accessibilityLiveRegion="polite"
      onPress={() => router.push('/sync')}
      style={{ backgroundColor: cfg.bg, paddingTop: insets.top, paddingHorizontal: 16 }}>
      <View style={{ minHeight: 36, flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <View>
          <Ionicons name={cfg.icon} size={16} color={cfg.fg} />
        </View>
        <Text style={{ flex: 1, fontFamily: font.semibold, fontSize: 13, color: cfg.fg }} numberOfLines={1}>
          {cfg.text}{getMock() ? ' · sample data' : ''}
        </Text>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
          <Ionicons name="time-outline" size={14} color={cfg.fg} />
          <Text style={{ fontFamily: font.bold, fontSize: 13, color: cfg.fg }}>{n} pending</Text>
          <Ionicons name="chevron-forward" size={14} color={cfg.fg} />
        </View>
      </View>
    </Pressable>
  );
}
