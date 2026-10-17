// Sync status (spec §8.2 / §8.4): pending queue (survives restart — SQLite), Sync now button, per-action results
// in plain language (applied / rejected + reason). Remove a pending action with confirmation.
import { Ionicons } from '@expo/vector-icons';
import { useState } from 'react';
import { Alert, ScrollView, View } from 'react-native';
import { describeResult, removeQueued, syncNow, useSync } from '../lib/sync';
import { palette } from '../lib/theme';
import { HexButton, Notice, SectionTitle, styles, T } from '../ui/kit';

export default function SyncScreen() {
  const { mode, pending, lastResults, lastSyncError } = useSync();
  const [note, setNote] = useState<string | null>(null);

  async function run() {
    setNote(null);
    const r = await syncNow();
    if (r) {
      const ok = r.filter((x) => x.status === 'applied').length, bad = r.filter((x) => x.status === 'rejected').length;
      setNote(`Sync finished: ${ok} saved, ${bad} not saved${r.length - ok - bad ? `, ${r.length - ok - bad} already on the server` : ''}.`);
    }
  }

  return (
    <ScrollView style={styles.page} contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
      <View style={[styles.card, { flexDirection: 'row', alignItems: 'center', gap: 12 }]} accessible accessibilityLabel={`Status ${mode}. ${pending.length} pending`}>
        <Ionicons name={mode === 'offline' ? 'cloud-offline' : mode === 'syncing' ? 'sync' : 'cloud-done'} size={32} color={mode === 'offline' ? '#7A5A00' : palette.live} />
        <View style={{ flex: 1 }}>
          <T kind="title">{mode === 'offline' ? 'Offline' : mode === 'syncing' ? 'Syncing…' : 'Online'}</T>
          <T kind="muted">{pending.length} pending {pending.length === 1 ? 'action' : 'actions'} · syncs automatically when online</T>
        </View>
      </View>
      <HexButton testID="sync-now" kind="accent" icon="sync" label="Sync now" onPress={run} loading={mode === 'syncing'} disabled={pending.length === 0 || mode === 'offline'} />
      {mode === 'offline' && pending.length ? <T kind="muted" style={{ marginTop: 6 }}>You are offline. Pending actions will be sent when the connection is back.</T> : null}
      {note ? <Notice kind="ok" text={note} testID="sync-note" /> : null}
      {lastSyncError ? <Notice kind="error" text={lastSyncError} testID="sync-error" /> : null}

      <SectionTitle>{`PENDING (${pending.length})`}</SectionTitle>
      {pending.length === 0 ? <T kind="muted">Nothing waiting. Actions you make while offline appear here.</T> : pending.map((p) => (
        <View key={p.action.action_id} testID={`pending-${p.action.action_id}`} style={[styles.card, { flexDirection: 'row', alignItems: 'center', gap: 8 }]}>
          <Ionicons name="time-outline" size={22} color={palette.ink2} />
          <View style={{ flex: 1 }}>
            <T>{p.label}</T>
            <T kind="muted">Pending · {p.action.type === 'score_event' ? 'Scoring' : 'Roster'} · queued {p.action.queued_at.replace('T', ' ').replace('Z', ' UTC')}</T>
          </View>
          <HexButton testID={`pending-remove-${p.action.action_id}`} kind="secondary" label="Remove" style={{ width: 110 }} a11y={`Remove pending action ${p.label}`}
            onPress={() => Alert.alert('Remove this pending action?', 'It will not be sent to the server.', [{ text: 'Keep', style: 'cancel' }, { text: 'Remove', style: 'destructive', onPress: () => removeQueued(p.action.action_id) }])} />
        </View>
      ))}

      <SectionTitle>LAST RESULTS</SectionTitle>
      {lastResults.length === 0 ? <T kind="muted">No synced actions yet.</T> : lastResults.map((r) => (
        <View key={r.action_id} testID={`result-${r.action_id}`} style={[styles.card, { flexDirection: 'row', alignItems: 'center', gap: 8 }]}
          accessible accessibilityLabel={`${r.label}. ${r.status}. ${describeResult(r)}`}>
          <Ionicons name={r.status === 'applied' ? 'checkmark-circle' : r.status === 'duplicate' ? 'copy-outline' : 'close-circle'} size={24} color={r.status === 'rejected' ? palette.redDark : palette.live} />
          <View style={{ flex: 1 }}>
            <T>{r.label}</T>
            <T kind="small">{r.status === 'applied' ? 'Applied' : r.status === 'duplicate' ? 'Duplicate' : 'Rejected'} — {describeResult(r)}</T>
          </View>
        </View>
      ))}
    </ScrollView>
  );
}
