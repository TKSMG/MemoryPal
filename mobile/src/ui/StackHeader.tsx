/**
 * The bar above every pushed page (Review, Quick quiz, Settings, a set...),
 * drawn by the app instead of the phone's own navigation bar.
 *
 * Why: the tab pages have no bar, so opening a page from a tab made the
 * phone switch its bar on part-way through the slide. The page was laid out
 * once without the bar and again with it, and the bar's height was only
 * reported back after the slide had finished, so the title, the back button
 * and the top of the page shifted into place a moment after the animation
 * ended (iPhone and Android alike). This bar is part of the page itself, its
 * size is known before the first frame (a fixed height plus the status bar
 * inset), and it slides in with the page, so nothing moves afterwards.
 *
 * Sheets (New set, Edit card, AI features) keep the phone's own bar: they
 * have no tab page underneath, so they never had the jump.
 */
import Ionicons from '@expo/vector-icons/Ionicons';
import type { NativeStackHeaderProps } from 'expo-router/build/react-navigation/native-stack';
import { Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useTheme } from './theme';

const IOS = Platform.OS === 'ios';
/** The bar's own height under the status bar: Apple's 44pt (50 on iPad), Material's 56dp. */
export const BAR_HEIGHT = Platform.OS === 'ios' ? (Platform.isPad ? 50 : 44) : 56;
/** Room each side of a centred title, so a long one never runs under the back button. */
const SIDE = 56;

export function StackHeader({ back, options, route, navigation }: NativeStackHeaderProps) {
  const theme = useTheme();
  const c = theme.colors;
  const insets = useSafeAreaInsets();
  const title = typeof options.title === 'string' ? options.title : route.name;
  const showBack = !!back && options.headerBackVisible !== false;
  const right = options.headerRight?.({ tintColor: c.link, canGoBack: !!back });
  return (
    <View
      style={{
        backgroundColor: c.bg,
        paddingTop: insets.top,
        paddingLeft: insets.left,
        paddingRight: insets.right,
      }}
    >
      <View style={[styles.bar, { height: BAR_HEIGHT }]}>
        {/* The title sits in its own layer, centred on the whole bar on iPhone like the system one. */}
        <View pointerEvents="none" style={[StyleSheet.absoluteFill, styles.titleLayer, IOS ? styles.titleCentre : { paddingLeft: showBack ? SIDE + 16 : 16, paddingRight: SIDE }]}>
          <Text
            accessibilityRole="header"
            numberOfLines={1}
            maxFontSizeMultiplier={1.4}
            style={{ color: c.ink, fontSize: IOS ? 17 : 20, fontWeight: '600', textAlign: IOS ? 'center' : 'left' }}
          >
            {title}
          </Text>
        </View>
        <View style={styles.side}>
          {showBack ? (
            <Pressable
              onPress={() => navigation.goBack()}
              accessibilityRole="button"
              accessibilityLabel={back?.title ? `Back to ${back.title}` : 'Back'}
              hitSlop={8}
              style={({ pressed }) => [styles.back, { opacity: pressed ? 0.5 : 1 }]}
            >
              <Ionicons name={IOS ? 'chevron-back' : 'arrow-back'} size={IOS ? 30 : 24} color={c.link} />
            </Pressable>
          ) : null}
        </View>
        <View style={[styles.side, styles.sideRight]}>{right}</View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  titleLayer: { justifyContent: 'center' },
  titleCentre: { alignItems: 'center', paddingHorizontal: SIDE + 8 },
  side: { minWidth: SIDE, height: '100%', flexDirection: 'row', alignItems: 'center' },
  sideRight: { justifyContent: 'flex-end', paddingRight: 12 },
  back: { height: '100%', paddingLeft: IOS ? 6 : 16, paddingRight: 12, justifyContent: 'center' },
});
