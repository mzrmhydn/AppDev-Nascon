// Settings (spec §8.1): editable server address (emulator 10.0.2.2:8080 / phone LAN IP), connection test,
// sample-data mode, sign out. Reachable from Login and from the Me tab.
import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, ScrollView, Switch, View } from 'react-native';
import * as api from '../lib/api';
import { DEFAULT_SERVER, getMock, getServer, setMock, setServer } from '../lib/config';
import { messageOf } from '../lib/errors';
import { signOut, useSession } from '../lib/session';
import { palette } from '../lib/theme';
import { Field, HexButton, Notice, SectionTitle, styles, T } from '../ui/kit';

export default function Settings() {
  const { user } = useSession();
  const [url, setUrl] = useState(getServer());
  const [mock, setMockState] = useState(getMock());
  const [msg, setMsg] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function saveAndTest() {
    const saved = setServer(url);
    setUrl(saved);
    setBusy(true); setMsg(null);
    try { await api.ping(); setMsg({ kind: 'ok', text: `Saved. The server at ${saved} is reachable.` }); }
    catch (e) { setMsg({ kind: 'error', text: `Saved, but: ${messageOf(e)}` }); }
    finally { setBusy(false); }
  }

  return (
    <ScrollView style={styles.page} contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
      <SectionTitle>SERVER ADDRESS</SectionTitle>
      <T kind="muted" style={{ marginBottom: 8 }}>Emulator: http://10.0.2.2:8080 · Phone: http://&lt;laptop LAN IP&gt;:8080</T>
      <Field label="Server address" testID="settings-server-url" value={url} onChangeText={setUrl} autoCapitalize="none" autoCorrect={false} keyboardType="url" />
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <HexButton testID="settings-save" label="Save & test" onPress={saveAndTest} loading={busy} style={{ flex: 1 }} />
        <HexButton testID="settings-reset" kind="secondary" label="Default" onPress={() => setUrl(DEFAULT_SERVER)} style={{ flex: 1 }} a11y="Fill in the default emulator address" />
      </View>
      {msg ? <Notice kind={msg.kind} text={msg.text} testID="settings-message" /> : null}

      <SectionTitle>SAMPLE DATA</SectionTitle>
      <View style={[styles.card, { flexDirection: 'row', alignItems: 'center', gap: 12 }]}>
        <View style={{ flex: 1 }}>
          <T>Use built-in sample data</T>
          <T kind="muted">For trying the app without a server. Turn off for the real league.</T>
        </View>
        <Switch testID="settings-mock" accessibilityLabel="Use built-in sample data" value={mock}
          trackColor={{ true: palette.red, false: palette.gray20 }} thumbColor="#fff"
          onValueChange={(v) => { setMock(v); setMockState(v); if (user) signOut(); }} />
      </View>
      <T kind="muted">Switching signs you out so data from the two sources never mixes.</T>

      {user ? (
        <>
          <SectionTitle>ACCOUNT</SectionTitle>
          <T style={{ marginBottom: 8 }}>Signed in as {user.email}</T>
          <HexButton testID="settings-signout" kind="danger" icon="log-out-outline" label="Sign out"
            onPress={() => Alert.alert('Sign out?', 'Actions waiting to sync stay saved on this phone.', [
              { text: 'Cancel', style: 'cancel' },
              { text: 'Sign out', style: 'destructive', onPress: async () => { await signOut(); router.replace('/login'); } },
            ])} />
        </>
      ) : null}
    </ScrollView>
  );
}
