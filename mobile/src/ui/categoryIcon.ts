// Store category → icon (products have no images in v1, contract §2.7).
import { Ionicons } from '@expo/vector-icons';
export const CATEGORY_ICON: Record<string, keyof typeof Ionicons.glyphMap> = { apparel: 'shirt-outline', accessory: 'watch-outline', digital: 'phone-portrait-outline' };
