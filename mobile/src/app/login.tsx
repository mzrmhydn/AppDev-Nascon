// Login (spec §8.2): email + password, demo-account quick-fill chips (§8.3), Sportify red hero header.
// Token goes to secure storage via session.signIn; role-aware tabs open afterwards.
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from 'react-native';
import { getMock, getServer } from '../lib/config';
import { messageOf } from '../lib/errors';
import { signIn } from '../lib/session';
import { font, palette, TAP } from '../lib/theme';
import { Chip, Field, HexButton, Notice, T } from '../ui/kit';
import { Appear } from '../ui/Appear';

const DEMO = [
  { email: 'admin@nascon.test', label: 'Super Admin' },
  { email: 'organizer@nascon.test', label: 'Organizer' },
  { email: 'manager@nascon.test', label: 'Club Manager' },
  { email: 'player@nascon.test', label: 'Player' },
  { email: 'viewer@nascon.test', label: 'Viewer' },
];

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!email.trim() || !password) { setError('Please enter your email and password.'); return; }
    setBusy(true); setError(null);
    try { await signIn(email, password); router.replace('/'); }
    catch (e) { setError(messageOf(e)); }
    finally { setBusy(false); }
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: palette.page }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ paddingBottom: 32 }}>
        <View style={{ backgroundColor: palette.red, paddingHorizontal: 16, paddingTop: 20, paddingBottom: 24, overflow: 'hidden' }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Ionicons name="football" size={26} color="#fff" />
            <Text style={{ fontFamily: font.display, fontSize: 28, color: '#fff', letterSpacing: 1 }}>NASCON LEAGUE</Text>
          </View>
          <Text accessibilityElementsHidden importantForAccessibility="no" style={{ position: 'absolute', right: -10, top: 30, fontFamily: font.display, fontSize: 120, color: 'rgba(255,255,255,0.15)' }}>SIGN IN</Text>
          <Appear>
            <Text accessibilityRole="header" style={{ fontFamily: font.display, fontSize: 38, color: '#fff', marginTop: 56, lineHeight: 40 }}>SIGN IN TO YOUR{'\n'}LEAGUE ACCOUNT</Text>
          </Appear>
        </View>

        <View style={{ padding: 16 }}>
          <Field label="Email" testID="login-email" value={email} onChangeText={setEmail} autoCapitalize="none" autoComplete="email" keyboardType="email-address" placeholder="you@example.com" />
          <View>
            <Field label="Password" testID="login-password" value={password} onChangeText={setPassword} secureTextEntry={!show} placeholder="Password" onSubmitEditing={submit} />
            <Pressable testID="login-toggle-password" accessibilityRole="button" accessibilityLabel={show ? 'Hide password' : 'Show password'}
              onPress={() => setShow(!show)} style={{ position: 'absolute', right: 0, top: 18, width: TAP, height: TAP, alignItems: 'center', justifyContent: 'center' }}>
              <Ionicons name={show ? 'eye-off-outline' : 'eye-outline'} size={22} color={palette.ink3} />
            </Pressable>
          </View>

          {error ? <Notice kind="error" text={error} testID="login-error" /> : null}
          <HexButton testID="login-submit" label="Sign in" onPress={submit} loading={busy} style={{ marginTop: 8 }} />

          <T kind="label" style={{ marginTop: 24, marginBottom: 8 }}>Demo accounts — tap to fill</T>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            {DEMO.map((d) => (
              <Chip key={d.email} testID={`login-demo-${d.label.replace(/\s/g, '-').toLowerCase()}`} label={d.label} sub={d.email}
                selected={email === d.email} onPress={() => { setEmail(d.email); setPassword('Nascon@26'); setError(null); }} />
            ))}
          </View>

          <HexButton testID="login-open-settings" kind="secondary" icon="settings-outline" label="Server settings" onPress={() => router.push('/settings')} style={{ marginTop: 24 }} />
          <T kind="muted" style={{ marginTop: 8, textAlign: 'center' }}>Server: {getMock() ? 'built-in sample data' : getServer()}</T>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
