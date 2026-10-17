// Design tokens from the Figma "Sportify" file (Colors section + text styles) + tenant white-label colours.
// Serves spec §8.6 "visual consistency" and FR-2.1: the tenant's primary_color replaces the red accent.
import { useSession } from './session';

export const palette = {
  ink: '#150000', // Sportify "Black" — main text, primary buttons
  ink2: '#322D2D', // Grays/100
  ink3: '#5B5757', // Grays/80 — secondary text (7:1 on #FAFAFA)
  ink4: '#848181', // Grays/60 — hints only
  gray40: '#ADABAB',
  gray20: '#D6D5D5', // secondary button / disabled
  gray10: '#EEEDED', // match-card panel
  page: '#FAFAFA', // Background
  surface: '#FFFFFF',
  red: '#FF5050', // "Pink Maybe" — default accent
  redDark: '#CC4040',
  maroon: '#2F0000',
  live: '#009C54',
  liveSoft: '#E3F4EB',
  warn: '#FFD100',
  warnSoft: '#FFF6CC',
  dangerSoft: '#FFE5E5',
};

export const font = {
  display: 'BebasNeue_400Regular', // headings, buttons, tags (always uppercase)
  regular: 'Manrope_400Regular',
  medium: 'Manrope_500Medium',
  semibold: 'Manrope_600SemiBold',
  bold: 'Manrope_700Bold',
};

// Figma type scale: Bebas 48/38/30/28/20/16, Manrope 24/20/16/14/12.
export const size = { hero: 38, h1: 30, h2: 24, h3: 20, body: 16, small: 14, tiny: 12 };

export const TAP = 48; // minimum tap target (spec §8.6: about 48 dp)
export const GAP = 16; // Figma page padding

function validHex(v: string | null | undefined): v is string {
  return !!v && /^#[0-9a-fA-F]{6}$/.test(v);
}

/** Accent colour of the logged-in tenant, falling back to Sportify red. */
export function useAccent() {
  const { tenant } = useSession();
  const accent = validHex(tenant?.primary_color) ? tenant!.primary_color : palette.red;
  return { accent, onAccent: onColor(accent) };
}

/** Readable text colour (ink/white) on a background hex. */
export function onColor(hex: string): string {
  if (!validHex(hex)) return '#fff';
  const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
  return (r * 299 + g * 587 + b * 114) / 1000 > 165 ? palette.ink : '#fff';
}

/** Stable crest colour for a team id when the server gives none. */
export function crestColor(id: string): string {
  const colors = ['#12233F', '#001B58', '#1E175E', '#009C54', '#CC4040', '#322D2D', '#005AFF', '#7A4B00'];
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  return colors[h % colors.length];
}

/** Money: integer paisa → "PKR 4,500.00". */
export function money(minor: number): string {
  return 'PKR ' + (minor / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** "2026-10-17T14:00:00Z" → "Sat 17 Oct · 19:00" in the phone's timezone. */
export function when(iso: string | null): string {
  if (!iso) return 'Time to be confirmed';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return 'Time to be confirmed';
  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${days[d.getDay()]} ${d.getDate()} ${months[d.getMonth()]} · ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}
