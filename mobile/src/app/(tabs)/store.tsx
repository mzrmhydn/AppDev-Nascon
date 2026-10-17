// Store catalogue (spec §8.2 Store): GET /api/v1/products (cached), category icon tiles, cart button with count.
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { FlatList, Pressable, RefreshControl, Text, useWindowDimensions, View } from 'react-native';
import * as api from '../../lib/api';
import { useCart } from '../../lib/stores';
import { font, money, palette } from '../../lib/theme';
import type { Product } from '../../lib/types';
import { useCached } from '../../lib/useCached';
import { CATEGORY_ICON } from '../../ui/categoryIcon';
import { CachedNotice, Empty, ErrorState, HexButton, Loading, styles, T } from '../../ui/kit';
import { Appear } from '../../ui/Appear';


function Tile({ p, w, i }: { p: Product; w: number; i: number }) {
  const min = Math.min(...p.variants.map((v) => v.price_minor));
  const inStock = p.variants.some((v) => v.stock > 0);
  return (
    <Appear kind="fade" delay={i * 40} style={{ width: w }}>
      <Pressable testID={`product-${p.product_id}`} accessibilityRole="button"
        accessibilityLabel={`${p.name}, ${p.category}, from ${money(min)}. ${inStock ? 'In stock' : 'Sold out'}. Open product`}
        onPress={() => router.push({ pathname: '/product/[id]', params: { id: p.product_id } })}
        style={({ pressed }) => ({ backgroundColor: palette.surface, opacity: pressed ? 0.85 : 1 })}>
        <View style={{ height: 110, backgroundColor: palette.gray10, alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name={CATEGORY_ICON[p.category] ?? 'pricetag-outline'} size={48} color={palette.ink2} />
          {!inStock ? <View style={{ position: 'absolute', top: 8, left: 8, backgroundColor: palette.ink, paddingHorizontal: 6, paddingVertical: 2 }}><Text style={{ color: '#fff', fontFamily: font.display }}>SOLD OUT</Text></View> : null}
        </View>
        <View style={{ padding: 10 }}>
          <Text style={{ fontFamily: font.semibold, fontSize: 14, color: palette.ink, minHeight: 38 }} numberOfLines={2}>{p.name}</Text>
          <T kind="label">{p.category}</T>
          <Text style={{ fontFamily: font.display, fontSize: 20, color: palette.ink, marginTop: 4 }}>{money(min)}</Text>
        </View>
      </Pressable>
    </Appear>
  );
}

export default function Store() {
  const res = useCached('products', api.listProducts);
  const cart = useCart();
  const { width } = useWindowDimensions();
  const cols = width >= 600 ? 3 : 2;
  const w = (width - 32 - (cols - 1) * 12) / cols;
  const count = cart.reduce((s, l) => s + l.quantity, 0);

  let body;
  if (res.loading && !res.data) body = <Loading label="Loading store…" />;
  else if (res.error && !res.data) body = <ErrorState message={res.error} onRetry={res.reload} testID="store-retry" />;

  return (
    <View style={styles.page}>
      <FlatList
        key={cols}
        data={body ? [] : res.data?.products ?? []}
        numColumns={cols}
        columnWrapperStyle={{ gap: 12, paddingHorizontal: 16 }}
        contentContainerStyle={{ gap: 12, paddingBottom: 96 }}
        keyExtractor={(p) => p.product_id}
        renderItem={({ item, index }) => <Tile p={item} w={w} i={index} />}
        refreshControl={<RefreshControl refreshing={res.loading && !!res.data} onRefresh={res.reload} />}
        ListHeaderComponent={
          <View style={{ padding: 16, paddingBottom: 0 }}>
            <T kind="display" accessibilityRole="header" style={{ fontSize: 34 }}>CLUB STORE</T>
            <T kind="muted">Official merchandise. Prices in PKR.</T>
            <CachedNotice savedAt={res.fromCache} />
          </View>
        }
        ListEmptyComponent={body ?? <Empty icon="bag-outline" title="No products yet" hint="Check back soon." />}
      />
      {count > 0 ? (
        <Appear style={{ position: 'absolute', left: 16, right: 16, bottom: 16 }}>
          <HexButton testID="store-open-cart" kind="accent" icon="cart" label={`View cart (${count})`} onPress={() => router.push('/cart')} />
        </Appear>
      ) : null}
    </View>
  );
}
