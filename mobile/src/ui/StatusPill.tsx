// Match status pill: icon + word for upcoming / live / full time (never colour alone, spec §8.6).
import { Ionicons } from '@expo/vector-icons';
import { Text, View } from 'react-native';
import { font, palette } from '../lib/theme';
import type { Fixture } from '../lib/types';

const STATUS_TEXT = { upcoming: 'Upcoming', in_progress: 'Live', completed: 'Full time' } as const;

export function StatusPill({ status }: { status: Fixture['status'] }) {
  const live = status === 'in_progress';
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: live ? palette.live : status === 'completed' ? palette.ink : palette.gray20, paddingHorizontal: 8, paddingVertical: 4 }}>
      <Ionicons name={live ? 'radio' : status === 'completed' ? 'flag' : 'time-outline'} size={12} color={status === 'upcoming' ? palette.ink : '#fff'} />
      <Text style={{ fontFamily: font.semibold, fontSize: 12, color: status === 'upcoming' ? palette.ink : '#fff' }}>{STATUS_TEXT[status]}</Text>
    </View>
  );
}

