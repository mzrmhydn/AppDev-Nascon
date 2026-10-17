// Shared UI kit in the Sportify style: Bebas headings, hex-ended buttons, red-underline tabs, crest badges,
// loading / empty / error states. Spec §8.6: one look everywhere, 48 dp targets, labels on everything.
import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import { Appear } from './Appear';
import {
  ActivityIndicator, Pressable, StyleSheet, Text, TextInput, TextInputProps, TextProps, View, ViewStyle,
} from 'react-native';
import { crestColor, font, GAP, onColor, palette, size, TAP, useAccent } from '../lib/theme';

export function T({ style, kind = 'body', ...p }: TextProps & { kind?: 'display' | 'title' | 'body' | 'muted' | 'small' | 'label' }) {
  return <Text {...p} style={[styles[kind], style]} maxFontSizeMultiplier={1.4} />;
}

type BtnKind = 'primary' | 'accent' | 'secondary' | 'danger';
/** Hexagon-ended button from the Figma "Button" component. */
export function HexButton({ label, onPress, kind = 'primary', disabled, loading, testID, icon, style, a11y }: {
  label: string; onPress: () => void; kind?: BtnKind; disabled?: boolean; loading?: boolean; testID: string;
  icon?: keyof typeof Ionicons.glyphMap; style?: ViewStyle; a11y?: string;
}) {
  const { accent } = useAccent();
  const bg = disabled ? palette.gray20 : kind === 'primary' ? palette.ink : kind === 'accent' ? accent : kind === 'danger' ? palette.redDark : palette.gray20;
  const fg = disabled ? palette.ink4 : kind === 'secondary' ? palette.ink : onColor(bg);
  const h = 48, tip = 12;
  return (
    <Pressable
      testID={testID} accessibilityRole="button" accessibilityLabel={a11y ?? label}
      accessibilityState={{ disabled: !!disabled || !!loading, busy: !!loading }}
      disabled={disabled || loading} onPress={onPress}
      style={({ pressed }) => [{ flexDirection: 'row', height: h, opacity: pressed ? 0.8 : 1, transform: [{ scale: pressed ? 0.98 : 1 }] }, style]}>
      <View style={{ width: 0, height: 0, borderTopWidth: h / 2, borderBottomWidth: h / 2, borderRightWidth: tip, borderTopColor: 'transparent', borderBottomColor: 'transparent', borderRightColor: bg }} />
      <View style={{ flex: 1, backgroundColor: bg, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }}>
        {loading ? <ActivityIndicator color={fg} /> : icon ? <Ionicons name={icon} size={18} color={fg} /> : null}
        <Text style={{ fontFamily: font.display, fontSize: 20, color: fg, letterSpacing: 0.5 }} numberOfLines={1}>{label}</Text>
      </View>
      <View style={{ width: 0, height: 0, borderTopWidth: h / 2, borderBottomWidth: h / 2, borderLeftWidth: tip, borderTopColor: 'transparent', borderBottomColor: 'transparent', borderLeftColor: bg }} />
    </Pressable>
  );
}

/** Small red hex tag (Figma "FOOTBALL ▾" pill). */
export function Tag({ label, color, testID, onPress, a11y }: { label: string; color?: string; testID?: string; onPress?: () => void; a11y?: string }) {
  const { accent } = useAccent();
  const bg = color ?? accent, h = 32, tip = 8;
  const body = (
    <View style={{ flexDirection: 'row', height: h, minWidth: 48 }}>
      <View style={{ borderTopWidth: h / 2, borderBottomWidth: h / 2, borderRightWidth: tip, borderTopColor: 'transparent', borderBottomColor: 'transparent', borderRightColor: bg }} />
      <View style={{ backgroundColor: bg, justifyContent: 'center', paddingHorizontal: 6, flexDirection: 'row', alignItems: 'center', gap: 4 }}>
        <Text style={{ fontFamily: font.display, fontSize: 16, color: onColor(bg) }}>{label}</Text>
        {onPress ? <Ionicons name="chevron-down" size={14} color={onColor(bg)} /> : null}
      </View>
      <View style={{ borderTopWidth: h / 2, borderBottomWidth: h / 2, borderLeftWidth: tip, borderTopColor: 'transparent', borderBottomColor: 'transparent', borderLeftColor: bg }} />
    </View>
  );
  if (!onPress) return body;
  return <Pressable testID={testID} accessibilityRole="button" accessibilityLabel={a11y ?? label} onPress={onPress} hitSlop={8} style={{ minHeight: TAP, justifyContent: 'center' }}>{body}</Pressable>;
}

/** Underlined tab strip (Figma "Upcoming / Past Matches" and "Overview / Stats"). */
export function Tabs<K extends string>({ tabs, value, onChange, testID }: { tabs: { key: K; label: string }[]; value: K; onChange: (k: K) => void; testID: string }) {
  const { accent } = useAccent();
  return (
    <View style={{ flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: palette.gray20 }} accessibilityRole="tablist">
      {tabs.map((t) => {
        const on = t.key === value;
        return (
          <Pressable key={t.key} testID={`${testID}-${t.key}`} accessibilityRole="tab" accessibilityLabel={t.label} accessibilityState={{ selected: on }}
            onPress={() => onChange(t.key)} style={{ minHeight: TAP, paddingHorizontal: 12, justifyContent: 'center', borderBottomWidth: 3, borderBottomColor: on ? accent : 'transparent', marginBottom: -1 }}>
            <Text style={{ fontFamily: on ? font.semibold : font.medium, fontSize: size.body, color: on ? palette.ink : palette.ink3 }}>{t.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

/** Round team crest with initials (no logos in v1 — contract §2.1). */
export function Crest({ id, name, color, big }: { id: string; name: string; color?: string | null; big?: boolean }) {
  const bg = color && /^#[0-9a-fA-F]{6}$/.test(color) ? color : crestColor(id);
  const d = big ? 56 : 32;
  const initials = name.split(/\s+/).filter(Boolean).map((w) => w[0]).join('').slice(0, 3).toUpperCase();
  return (
    <View accessibilityElementsHidden importantForAccessibility="no" style={{ width: d, height: d, borderRadius: d / 2, backgroundColor: bg, alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: '#fff' }}>
      <Text style={{ fontFamily: font.display, fontSize: big ? 22 : 14, color: onColor(bg) }}>{initials}</Text>
    </View>
  );
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <View style={styles.center} accessibilityLiveRegion="polite" accessibilityLabel={label}>
      <ActivityIndicator size="large" color={palette.ink} />
      <T kind="muted" style={{ marginTop: 12 }}>{label}</T>
    </View>
  );
}

export function Empty({ icon = 'information-circle-outline', title, hint }: { icon?: keyof typeof Ionicons.glyphMap; title: string; hint?: string }) {
  return (
    <View style={styles.center}>
      <Ionicons name={icon} size={40} color={palette.ink4} />
      <T kind="title" style={{ marginTop: 8, textAlign: 'center' }}>{title}</T>
      {hint ? <T kind="muted" style={{ textAlign: 'center', marginTop: 4 }}>{hint}</T> : null}
    </View>
  );
}

export function ErrorState({ message, onRetry, testID }: { message: string; onRetry?: () => void; testID: string }) {
  return (
    <View style={styles.center} accessibilityLiveRegion="assertive">
      <Ionicons name="alert-circle-outline" size={40} color={palette.redDark} />
      <T kind="title" style={{ marginTop: 8 }}>Couldn’t load this</T>
      <T kind="muted" style={{ textAlign: 'center', marginVertical: 8 }}>{message}</T>
      {onRetry ? <HexButton testID={testID} label="Try again" icon="refresh" onPress={onRetry} style={{ width: 200 }} /> : null}
    </View>
  );
}

/** "Showing saved copy" notice when a screen is served from the SQLite cache. */
export function CachedNotice({ savedAt }: { savedAt: string | null }) {
  if (!savedAt) return null;
  return (
    <View style={styles.notice} accessibilityLabel={`Offline. Showing saved data from ${savedAt}`}>
      <Ionicons name="save-outline" size={16} color={palette.ink2} />
      <T kind="small">Showing saved data from {savedAt.replace('T', ' ').replace('Z', ' UTC')}</T>
    </View>
  );
}

/** Message box: kind decides icon + background (meaning never by colour alone — always an icon + text). */
export function Notice({ kind, text, testID }: { kind: 'ok' | 'error' | 'info' | 'warn'; text: string; testID?: string }) {
  const map = {
    ok: { icon: 'checkmark-circle', bg: palette.liveSoft, fg: palette.live },
    error: { icon: 'close-circle', bg: palette.dangerSoft, fg: palette.redDark },
    warn: { icon: 'warning', bg: palette.warnSoft, fg: '#7A5A00' },
    info: { icon: 'information-circle', bg: palette.gray10, fg: palette.ink2 },
  }[kind] as { icon: keyof typeof Ionicons.glyphMap; bg: string; fg: string };
  return (
    <Appear testID={testID}
      style={[styles.notice, { backgroundColor: map.bg }]} accessibilityLiveRegion="polite">
      <Ionicons name={map.icon} size={20} color={map.fg} />
      <T style={{ flex: 1, color: palette.ink }}>{text}</T>
    </Appear>
  );
}

export function Field({ label, testID, ...p }: TextInputProps & { label: string; testID: string }) {
  return (
    <View style={{ marginBottom: 12 }}>
      <T kind="label" style={{ marginBottom: 4 }}>{label}</T>
      <TextInput testID={testID} accessibilityLabel={label} placeholderTextColor={palette.ink4}
        style={{ minHeight: TAP, backgroundColor: '#F1F1F1', paddingHorizontal: 14, fontFamily: font.medium, fontSize: size.body, color: palette.ink }} {...p} />
    </View>
  );
}

/** Selectable chip (option pickers). Selected = filled + check icon. */
export function Chip({ label, selected, onPress, testID, disabled, sub }: { label: string; selected?: boolean; onPress: () => void; testID: string; disabled?: boolean; sub?: string }) {
  const { accent } = useAccent();
  return (
    <Pressable testID={testID} accessibilityRole="button" accessibilityLabel={sub ? `${label}, ${sub}` : label} accessibilityState={{ selected: !!selected, disabled: !!disabled }}
      disabled={disabled} onPress={onPress}
      style={{ minHeight: TAP, minWidth: TAP, paddingHorizontal: 14, paddingVertical: 6, borderWidth: 2, borderColor: selected ? accent : palette.gray20, backgroundColor: selected ? accent : palette.surface, opacity: disabled ? 0.5 : 1, flexDirection: 'row', alignItems: 'center', gap: 6 }}>
      {selected ? <Ionicons name="checkmark" size={16} color={onColor(accent)} /> : null}
      <View>
        <Text style={{ fontFamily: font.semibold, fontSize: size.small, color: selected ? onColor(accent) : palette.ink }}>{label}</Text>
        {sub ? <Text style={{ fontFamily: font.regular, fontSize: size.tiny, color: selected ? onColor(accent) : palette.ink3 }}>{sub}</Text> : null}
      </View>
    </Pressable>
  );
}

export function SectionTitle({ children, right }: { children: string; right?: React.ReactNode }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 20, marginBottom: 8 }}>
      <Text accessibilityRole="header" style={{ fontFamily: font.display, fontSize: size.h2, color: palette.ink }}>{children}</Text>
      {right}
    </View>
  );
}

export const styles = StyleSheet.create({
  display: { fontFamily: font.display, fontSize: size.h1, color: palette.ink, letterSpacing: 0.3 },
  title: { fontFamily: font.semibold, fontSize: size.h3, color: palette.ink },
  body: { fontFamily: font.medium, fontSize: size.body, color: palette.ink },
  muted: { fontFamily: font.regular, fontSize: size.small, color: palette.ink3 },
  small: { fontFamily: font.medium, fontSize: size.small, color: palette.ink2 },
  label: { fontFamily: font.semibold, fontSize: size.tiny, color: palette.ink3, letterSpacing: 0.6, textTransform: 'uppercase' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, minHeight: 240 },
  notice: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 12, backgroundColor: palette.gray10, marginVertical: 8 },
  page: { flex: 1, backgroundColor: palette.page },
  pad: { paddingHorizontal: GAP },
  card: { backgroundColor: palette.surface, padding: GAP, marginBottom: 12 },
});
