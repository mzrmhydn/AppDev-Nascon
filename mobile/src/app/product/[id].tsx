// Product detail + variant picker (spec §8.2 Store): size / colour chips, live stock (GET /audit/v1/inventory),
// quantity stepper (1..10), add to cart.
import { Ionicons } from '@expo/vector-icons';
import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import * as api from '../../lib/api';
import { cacheGet } from '../../lib/db';
import { addToCart } from '../../lib/stores';
import { font, money, palette, TAP } from '../../lib/theme';
import type { Product } from '../../lib/types';
import { Chip, Empty, HexButton, Notice, SectionTitle, styles, T } from '../../ui/kit';
import { CATEGORY_ICON } from '../../ui/categoryIcon';

export default function ProductScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [product, setProduct] = useState<Product | null>(() => cacheGet<{ products: Product[] }>('products')?.data.products.find((p) => p.product_id === id) ?? null);
  const [variantId, setVariantId] = useState<string | null>(null);
  const [qty, setQty] = useState(1);
  const [stock, setStock] = useState<number | null>(null);
  const [added, setAdded] = useState(false);

  useEffect(() => {
    if (!product) api.listProducts().then((r) => setProduct(r.products.find((p) => p.product_id === id) ?? null)).catch(() => {});
  }, [id, product]);
  useEffect(() => {
    if (product && !variantId) setVariantId((product.variants.find((v) => v.stock > 0) ?? product.variants[0])?.variant_id ?? null);
  }, [product, variantId]);
  const variant = useMemo(() => product?.variants.find((v) => v.variant_id === variantId) ?? null, [product, variantId]);
  useEffect(() => {
    if (!variant) return;
    setStock(variant.stock);
    api.getInventory(variant.variant_id).then((i) => setStock(i.stock)).catch(() => {}); // fresh stock, falls back to list value
  }, [variant]);

  if (!product) return <Empty icon="bag-outline" title="Product not found" />;
  const label = (v: Product['variants'][number]) => [v.size, v.color].filter(Boolean).join(' · ') || 'Standard';
  const avail = stock ?? variant?.stock ?? 0;
  const max = Math.min(10, avail);

  return (
    <ScrollView style={styles.page} contentContainerStyle={{ paddingBottom: 32 }}>
      <Stack.Screen options={{ title: 'PRODUCT' }} />
      <View style={{ height: 180, backgroundColor: palette.gray10, alignItems: 'center', justifyContent: 'center' }} accessibilityElementsHidden>
        <Ionicons name={CATEGORY_ICON[product.category] ?? 'pricetag-outline'} size={80} color={palette.ink2} />
      </View>
      <View style={styles.pad}>
        <T kind="display" style={{ marginTop: 12 }} accessibilityRole="header">{product.name.toUpperCase()}</T>
        <T kind="muted">{product.description}</T>
        {variant ? <Text style={{ fontFamily: font.display, fontSize: 36, color: palette.ink, marginTop: 8 }} accessibilityLabel={`Price ${money(variant.price_minor)}`}>{money(variant.price_minor)}</Text> : null}

        <SectionTitle>CHOOSE OPTION</SectionTitle>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
          {product.variants.map((v) => (
            <Chip key={v.variant_id} testID={`variant-${v.variant_id}`} label={label(v)} sub={v.stock > 0 ? `${v.stock} left` : 'Sold out'}
              selected={v.variant_id === variantId} onPress={() => { setVariantId(v.variant_id); setQty(1); setAdded(false); }} />
          ))}
        </View>

        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 12 }}>
          <Ionicons name={avail > 0 ? 'checkmark-circle' : 'close-circle'} size={18} color={avail > 0 ? palette.live : palette.redDark} />
          <T>{avail > 0 ? `In stock — ${avail} available` : 'Sold out — choose another option'}</T>
        </View>

        <SectionTitle>QUANTITY</SectionTitle>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 16 }}>
          <Stepper icon="remove" label="Decrease quantity" testID="qty-minus" disabled={qty <= 1} onPress={() => setQty(qty - 1)} />
          <Text style={{ fontFamily: font.display, fontSize: 30, minWidth: 30, textAlign: 'center' }} accessibilityLabel={`Quantity ${qty}`}>{qty}</Text>
          <Stepper icon="add" label="Increase quantity" testID="qty-plus" disabled={qty >= max} onPress={() => setQty(qty + 1)} />
        </View>

        {added ? <Notice kind="ok" text="Added to your cart." testID="product-added" /> : null}
        <View style={{ gap: 12, marginTop: 20 }}>
          <HexButton testID="product-add" kind="accent" icon="cart-outline" label="Add to cart" disabled={!variant || avail <= 0}
            onPress={() => { if (variant) { addToCart(product, variant, qty); setAdded(true); } }} />
          {added ? <HexButton testID="product-go-cart" label="Go to cart" onPress={() => router.push('/cart')} /> : null}
        </View>
      </View>
    </ScrollView>
  );
}

function Stepper({ icon, label, onPress, disabled, testID }: { icon: 'add' | 'remove'; label: string; onPress: () => void; disabled?: boolean; testID: string }) {
  return (
    <Pressable testID={testID} accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: !!disabled }} disabled={disabled} onPress={onPress}
      style={{ width: TAP, height: TAP, backgroundColor: disabled ? palette.gray10 : palette.ink, alignItems: 'center', justifyContent: 'center' }}>
      <Ionicons name={icon} size={22} color={disabled ? palette.ink4 : '#fff'} />
    </Pressable>
  );
}
