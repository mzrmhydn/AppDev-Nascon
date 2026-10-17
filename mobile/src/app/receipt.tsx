// Receipt view + PDF download/share (spec §5.12 receipt.pdf_base64, §8.2 "receipt view/download").
import { Ionicons } from '@expo/vector-icons';
import { File, Paths } from 'expo-file-system';
import { router } from 'expo-router';
import * as Sharing from 'expo-sharing';
import { useState } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { cacheGet, kvGet } from '../lib/db';
import { font, money, palette } from '../lib/theme';
import type { CheckoutResponse, Product } from '../lib/types';
import { Empty, HexButton, Notice, styles, T } from '../ui/kit';
import { Appear } from '../ui/Appear';

export default function Receipt() {
  const raw = kvGet('last_receipt');
  const r: CheckoutResponse | null = raw ? JSON.parse(raw) : null;
  const [msg, setMsg] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  if (!r) return <Empty icon="receipt-outline" title="No receipt yet" />;

  const products = cacheGet<{ products: Product[] }>('products')?.data.products ?? [];
  const nameOf = (vid: string) => {
    const p = products.find((x) => x.variants.some((v) => v.variant_id === vid));
    const v = p?.variants.find((x) => x.variant_id === vid);
    return p ? `${p.name}${v && (v.size || v.color) ? ` (${[v.size, v.color].filter(Boolean).join(', ')})` : ''}` : vid;
  };

  async function sharePdf() {
    setBusy(true); setMsg(null);
    try {
      const file = new File(Paths.cache, `receipt-${r!.order_id}.pdf`);
      if (file.exists) file.delete();
      file.create();
      file.write(r!.receipt.pdf_base64, { encoding: 'base64' });
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(file.uri, { mimeType: 'application/pdf', dialogTitle: 'Save or share receipt', UTI: 'com.adobe.pdf' });
        setMsg({ kind: 'ok', text: 'Receipt PDF ready — choose where to save or share it.' });
      } else setMsg({ kind: 'error', text: 'Sharing is not available on this device.' });
    } catch {
      setMsg({ kind: 'error', text: 'The PDF could not be opened. Please try again.' });
    } finally { setBusy(false); }
  }

  return (
    <ScrollView style={styles.page} contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
      <Appear kind="zoom" style={{ alignItems: 'center', marginVertical: 12 }}>
        <Ionicons name="checkmark-circle" size={64} color={palette.live} />
        <T kind="display" accessibilityRole="header">PAYMENT SUCCESSFUL</T>
        <T kind="muted">Order {r.order_id}</T>
      </Appear>

      <View style={styles.card}>
        {r.items.map((i) => (
          <View key={i.variant_id} style={{ flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6, gap: 8 }}>
            <T style={{ flex: 1 }}>{i.quantity} × {nameOf(i.variant_id)}</T>
            <T>{money(i.quantity * i.unit_price_minor)}</T>
          </View>
        ))}
        <View style={{ borderTopWidth: 1, borderTopColor: palette.gray20, marginTop: 8, paddingTop: 8, gap: 4 }}>
          <Line k="Subtotal" v={money(r.subtotal_minor)} />
          {r.discount_minor ? <Line k="Discount" v={`− ${money(r.discount_minor)}`} /> : null}
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <T kind="title">Total paid</T>
            <Text style={{ fontFamily: font.display, fontSize: 32 }}>{money(r.total_minor)}</Text>
          </View>
          <Line k="Paid at" v={String(r.receipt.payload.paid_at ?? '').replace('T', ' ').replace('Z', ' UTC')} />
          <Line k="Payment" v={r.payment.state === 'captured' ? 'Captured' : r.payment.state} />
        </View>
        <T kind="muted" style={{ marginTop: 8 }} numberOfLines={1}>Signature {r.receipt.signature.slice(0, 16)}…</T>
      </View>

      {msg ? <Notice kind={msg.kind} text={msg.text} testID="receipt-message" /> : null}
      <View style={{ gap: 12, marginTop: 8 }}>
        <HexButton testID="receipt-share-pdf" kind="accent" icon="download-outline" label="Download / share PDF" onPress={sharePdf} loading={busy} />
        <HexButton testID="receipt-done" label="Back to store" onPress={() => router.navigate('/store')} />
      </View>
    </ScrollView>
  );
}

const Line = ({ k, v }: { k: string; v: string }) => (
  <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}><T kind="muted">{k}</T><T kind="small">{v}</T></View>
);
