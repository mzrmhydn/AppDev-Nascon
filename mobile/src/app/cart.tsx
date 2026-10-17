// Cart → confirm → checkout (spec §5.12 / §8.2): lines, quantity, WELCOME10-style discount field, mock card choice,
// confirmation dialog before paying, POST /api/v1/checkout with a client order_id (safe to retry: same id = replay).
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useRef, useState } from 'react';
import { Alert, Pressable, ScrollView, Text, View } from 'react-native';
import * as api from '../lib/api';
import { kvSet, newId } from '../lib/db';
import { ApiError, messageOf } from '../lib/errors';
import { useSession } from '../lib/session';
import { cartTotal, clearCart, setQty, useCart } from '../lib/stores';
import { font, money, palette, TAP } from '../lib/theme';
import { Chip, Empty, Field, HexButton, Notice, SectionTitle, styles, T } from '../ui/kit';

const CARDS = [
  { token: 'tok_success', label: 'Test card — approved', sub: '•••• 4242' },
  { token: 'tok_declined', label: 'Test card — declined', sub: '•••• 0002' },
  { token: 'tok_capture_fail', label: 'Test card — capture fails', sub: '•••• 0119' },
];

export default function Cart() {
  const lines = useCart();
  const { user } = useSession();
  const [code, setCode] = useState('');
  const [card, setCard] = useState(CARDS[0].token);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const orderId = useRef(newId('ord')); // kept across retries of the same cart → idempotent replay

  const subtotal = cartTotal(lines);
  if (!lines.length) return (
    <View style={styles.page}>
      <Empty icon="cart-outline" title="Your cart is empty" hint="Pick something from the store." />
      <View style={styles.pad}><HexButton testID="cart-browse" label="Browse store" onPress={() => router.navigate('/store')} /></View>
    </View>
  );

  async function pay() {
    setBusy(true); setError(null);
    try {
      const res = await api.postCheckout({
        order_id: orderId.current, customer_id: user?.user_id ?? 'guest',
        items: lines.map((l) => ({ variant_id: l.variant.variant_id, quantity: l.quantity })),
        discount_code: code.trim() ? code.trim().toUpperCase() : null, payment: { token: card },
      });
      kvSet('last_receipt', JSON.stringify(res));
      clearCart();
      router.replace('/receipt');
    } catch (e) {
      // a failed payment releases stock and must be retryable with a fresh order id
      if (e instanceof ApiError && e.status !== 0) orderId.current = newId('ord');
      setError(messageOf(e));
    } finally { setBusy(false); }
  }

  function confirm() {
    Alert.alert('Confirm payment', `Pay for ${lines.reduce((s, l) => s + l.quantity, 0)} item(s), subtotal ${money(subtotal)}${code.trim() ? ' (discount applied at checkout)' : ''}?`, [
      { text: 'Cancel', style: 'cancel' }, { text: 'Pay now', onPress: pay },
    ]);
  }

  return (
    <ScrollView style={styles.page} contentContainerStyle={{ padding: 16, paddingBottom: 40 }} keyboardShouldPersistTaps="handled">
      {lines.map((l) => (
        <View key={l.variant.variant_id} style={[styles.card, { flexDirection: 'row', alignItems: 'center', gap: 8 }]}>
          <View style={{ flex: 1 }}>
            <T numberOfLines={1}>{l.product.name}</T>
            <T kind="muted">{[l.variant.size, l.variant.color].filter(Boolean).join(' · ') || 'Standard'} · {money(l.variant.price_minor)}</T>
          </View>
          <Step icon={l.quantity === 1 ? 'trash-outline' : 'remove'} label={l.quantity === 1 ? `Remove ${l.product.name}` : `One less ${l.product.name}`} testID={`cart-minus-${l.variant.variant_id}`} onPress={() => setQty(l.variant.variant_id, l.quantity - 1)} />
          <Text style={{ fontFamily: font.display, fontSize: 22, width: 24, textAlign: 'center' }}>{l.quantity}</Text>
          <Step icon="add" label={`One more ${l.product.name}`} testID={`cart-plus-${l.variant.variant_id}`} disabled={l.quantity >= Math.min(10, l.variant.stock)} onPress={() => setQty(l.variant.variant_id, l.quantity + 1)} />
        </View>
      ))}

      <Field label="Discount code (optional)" testID="cart-discount" value={code} onChangeText={setCode} autoCapitalize="characters" placeholder="e.g. WELCOME10" />

      <SectionTitle>PAYMENT (TEST GATEWAY)</SectionTitle>
      <View style={{ gap: 8 }}>
        {CARDS.map((c) => <Chip key={c.token} testID={`cart-card-${c.token}`} label={c.label} sub={c.sub} selected={card === c.token} onPress={() => setCard(c.token)} />)}
      </View>

      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 20 }}>
        <T kind="title">Subtotal</T>
        <Text style={{ fontFamily: font.display, fontSize: 32 }}>{money(subtotal)}</Text>
      </View>
      {code.trim() ? <T kind="muted">Valid codes take 10% off. The final total is shown on your receipt.</T> : null}

      {error ? <Notice kind="error" text={error} testID="cart-error" /> : null}
      <HexButton testID="cart-pay" kind="accent" icon="lock-closed" label={`Pay ${money(subtotal)}`} onPress={confirm} loading={busy} style={{ marginTop: 16 }} />
    </ScrollView>
  );
}

function Step({ icon, label, onPress, disabled, testID }: { icon: keyof typeof Ionicons.glyphMap; label: string; onPress: () => void; disabled?: boolean; testID: string }) {
  return (
    <Pressable testID={testID} accessibilityRole="button" accessibilityLabel={label} disabled={disabled} onPress={onPress}
      style={{ width: TAP, height: TAP, alignItems: 'center', justifyContent: 'center', backgroundColor: disabled ? palette.gray10 : palette.gray20 }}>
      <Ionicons name={icon} size={20} color={disabled ? palette.ink4 : palette.ink} />
    </Pressable>
  );
}
