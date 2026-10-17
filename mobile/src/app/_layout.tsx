// Root layout: loads Sportify fonts, restores the session from secure storage, starts offline sync,
// shows the always-visible status banner above every screen, and sends logged-out users to Login.
import { BebasNeue_400Regular } from '@expo-google-fonts/bebas-neue';
import { Manrope_400Regular, Manrope_500Medium, Manrope_600SemiBold, Manrope_700Bold } from '@expo-google-fonts/manrope';
import { useFonts } from 'expo-font';
import { Redirect, Stack, useSegments } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { View } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { restore, useSession } from '../lib/session';
import { startSync } from '../lib/sync';
import { font, palette } from '../lib/theme';
import { StatusBanner } from '../ui/StatusBanner';

SplashScreen.preventAutoHideAsync().catch(() => {});

export default function RootLayout() {
  const [fontsLoaded] = useFonts({ BebasNeue_400Regular, Manrope_400Regular, Manrope_500Medium, Manrope_600SemiBold, Manrope_700Bold });
  const { ready, user } = useSession();
  const segments = useSegments();

  useEffect(() => { restore(); startSync(); }, []);
  useEffect(() => { if (fontsLoaded && ready) SplashScreen.hideAsync().catch(() => {}); }, [fontsLoaded, ready]);

  if (!fontsLoaded || !ready) return <View style={{ flex: 1, backgroundColor: palette.page }} />;

  const onLogin = segments[0] === 'login';
  const onSettings = segments[0] === 'settings';
  if (!user && !onLogin && !onSettings) return <Redirect href="/login" />;
  if (user && onLogin) return <Redirect href="/" />;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <StatusBar style="light" />
        <View style={{ flex: 1, backgroundColor: palette.page }}>
          <StatusBanner />
          <Stack
            screenOptions={{
              headerStyle: { backgroundColor: palette.page },
              headerShadowVisible: false,
              headerTintColor: palette.ink,
              headerTitleStyle: { fontFamily: font.display, fontSize: 24 },
              headerBackButtonDisplayMode: 'minimal',
              contentStyle: { backgroundColor: palette.page },
              statusBarTranslucent: false,
            }}>
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen name="login" options={{ headerShown: false }} />
            <Stack.Screen name="match/[id]" options={{ title: 'MATCH' }} />
            <Stack.Screen name="club/[id]" options={{ title: 'CLUB' }} />
            <Stack.Screen name="product/[id]" options={{ title: 'PRODUCT' }} />
            <Stack.Screen name="cart" options={{ title: 'CART' }} />
            <Stack.Screen name="receipt" options={{ title: 'RECEIPT', headerBackVisible: false }} />
            <Stack.Screen name="sync" options={{ title: 'SYNC STATUS' }} />
            <Stack.Screen name="settings" options={{ title: 'SETTINGS' }} />
          </Stack>
        </View>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
