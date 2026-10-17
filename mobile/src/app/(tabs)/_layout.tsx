// Role-aware bottom tabs (spec §8.2/§8.6 "right screen for the right role"): everyone gets Fixtures, Standings,
// Store, Club, Me; club_manager also Roster; league_organizer also Scoring; super_admin gets both.
import { Ionicons } from '@expo/vector-icons';
import { Tabs } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useSession } from '../../lib/session';
import { font, palette, useAccent } from '../../lib/theme';

type IconName = keyof typeof Ionicons.glyphMap;
const icon = (on: IconName, off: IconName) => ({ color, focused }: { color: any; focused: boolean }) =>
  <Ionicons name={focused ? on : off} size={24} color={color} />;

export default function TabsLayout() {
  const { user } = useSession();
  const { accent } = useAccent();
  const insets = useSafeAreaInsets();
  const role = user?.role;
  const roster = role === 'club_manager' || role === 'super_admin';
  const scoring = role === 'league_organizer' || role === 'super_admin';

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: accent,
        tabBarInactiveTintColor: palette.ink2,
        tabBarLabelStyle: { fontFamily: font.semibold, fontSize: 11 },
        tabBarStyle: { backgroundColor: palette.surface, borderTopColor: palette.gray20, height: 64 + insets.bottom, paddingTop: 6, paddingBottom: 6 + insets.bottom },
        tabBarItemStyle: { minHeight: 48 },
      }}>
      <Tabs.Screen name="index" options={{ title: 'Fixtures', tabBarButtonTestID: 'tab-fixtures', tabBarAccessibilityLabel: 'Fixtures tab', tabBarIcon: icon('calendar', 'calendar-outline') }} />
      <Tabs.Screen name="standings" options={{ title: 'Standings', tabBarButtonTestID: 'tab-standings', tabBarAccessibilityLabel: 'Standings tab', tabBarIcon: icon('podium', 'podium-outline') }} />
      <Tabs.Screen name="store" options={{ title: 'Store', tabBarButtonTestID: 'tab-store', tabBarAccessibilityLabel: 'Store tab', tabBarIcon: icon('bag-handle', 'bag-handle-outline') }} />
      <Tabs.Screen name="club" options={{ title: 'Club', tabBarButtonTestID: 'tab-club', tabBarAccessibilityLabel: 'Club tab', tabBarIcon: icon('shield', 'shield-outline') }} />
      <Tabs.Screen name="roster" options={{ href: roster ? undefined : null, title: 'Roster', tabBarButtonTestID: 'tab-roster', tabBarAccessibilityLabel: 'Roster management tab', tabBarIcon: icon('people', 'people-outline') }} />
      <Tabs.Screen name="scoring" options={{ href: scoring ? undefined : null, title: 'Scoring', tabBarButtonTestID: 'tab-scoring', tabBarAccessibilityLabel: 'Scoring entry tab', tabBarIcon: icon('stopwatch', 'stopwatch-outline') }} />
      <Tabs.Screen name="me" options={{ title: 'Me', tabBarButtonTestID: 'tab-me', tabBarAccessibilityLabel: 'My profile and settings tab', tabBarIcon: icon('person', 'person-outline') }} />
    </Tabs>
  );
}
