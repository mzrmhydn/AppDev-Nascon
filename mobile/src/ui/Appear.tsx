// Subtle entrance motion with Reanimated layout animations (fade/slide/zoom). Spec §8.6 feedback; no logic.
import Animated, { FadeIn, FadeInDown, ZoomIn } from 'react-native-reanimated';
import type { ViewProps } from 'react-native';

export function Appear({ delay = 0, kind = 'up', ...p }: ViewProps & { delay?: number; kind?: 'up' | 'fade' | 'zoom' }) {
  const base = kind === 'zoom' ? ZoomIn.springify() : kind === 'fade' ? FadeIn.duration(220) : FadeInDown.duration(260);
  return <Animated.View entering={base.delay(delay)} {...p} />;
}
