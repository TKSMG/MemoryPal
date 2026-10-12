/** Building blocks shared by every screen: calm, large, and accessible by default. */
import Ionicons from '@expo/vector-icons/Ionicons';
import { ReactNode } from 'react';
import {
  Pressable,
  ScrollView,
  StyleProp,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TextInputProps,
  TextStyle,
  useWindowDimensions,
  View,
  ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Theme, useTheme } from './theme';

export type IconName = keyof typeof Ionicons.glyphMap;

// ---------------------------------------------------------------- text
type Variant = 'title' | 'h2' | 'h3' | 'body' | 'muted' | 'label' | 'small' | 'big';

// Apple's text styles: Large Title 34, Title 2 22, Headline 17 semibold,
// Body 17, Subheadline 15, Footnote 13. Body keeps a roomier 24pt line for
// longer reading.
const SIZES: Record<Variant, [number, TextStyle['fontWeight'], number]> = {
  title: [34, '700', 41],
  big: [40, '700', 46],
  h2: [22, '700', 28],
  h3: [17, '600', 22],
  body: [17, '400', 24],
  muted: [15, '400', 20],
  label: [13, '600', 18],
  small: [13, '400', 18],
};

export function Txt({ variant = 'body', color, style, children, center, ...rest }: { variant?: Variant; color?: string; style?: StyleProp<TextStyle>; children: ReactNode; center?: boolean; numberOfLines?: number; accessibilityRole?: 'header' | 'text' }) {
  const theme = useTheme();
  const [size, weight, line] = SIZES[variant];
  // Big headings grow less than body text with the in-app text size, so a
  // page title still fits on one line on a small phone.
  const grow = variant === 'title' || variant === 'big' ? Math.min(theme.scale, 1.1) / theme.scale : 1;
  const tone = color ?? (variant === 'muted' || variant === 'small' || variant === 'label' ? theme.colors.muted : theme.colors.ink);
  return (
    <Text
      maxFontSizeMultiplier={2}
      accessibilityRole={rest.accessibilityRole ?? (variant === 'title' || variant === 'h2' ? 'header' : undefined)}
      style={[
        { color: tone, fontSize: theme.font(size * grow), lineHeight: theme.font(line * grow), fontWeight: weight },
        center && { textAlign: 'center' },
        style,
      ]}
      numberOfLines={rest.numberOfLines}
    >
      {children}
    </Text>
  );
}

// -------------------------------------------------------------- screen
/** Lines stay readable on iPad and in landscape: content stops growing here and centres. */
const READABLE_WIDTH = 720;

export function Screen({ title, eyebrow, right, children, scroll = true, padded = true }: { title?: string; eyebrow?: string; right?: ReactNode; children: ReactNode; scroll?: boolean; padded?: boolean }) {
  const theme = useTheme();
  const header = title ? (
    <View style={styles.header}>
      <View style={{ flex: 1 }}>
        {eyebrow ? <Txt variant="label" color={theme.colors.link}>{eyebrow}</Txt> : null}
        <Txt variant="title">{title}</Txt>
      </View>
      {right}
    </View>
  ) : null;
  const { width } = useWindowDimensions();
  // Side margins follow the screen: tighter on small phones so nothing is
  // squeezed, roomier on tablets (where content also stops at a readable width).
  const gutter = width < 360 ? 16 : width >= 600 ? 28 : 20;
  const pad = padded ? { paddingHorizontal: gutter } : null;
  // The native safe area view pads only where the screen really meets the
  // status bar or home indicator, so screens under a navigation bar or above
  // the tab bar get no extra gap.
  return (
    <SafeAreaView edges={['top', 'bottom', 'left', 'right']} style={{ flex: 1, backgroundColor: theme.colors.bg }}>
      {scroll ? (
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={[styles.readable, { paddingTop: 12, paddingBottom: 32, gap: 16 }, pad]}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="interactive"
          automaticallyAdjustKeyboardInsets
        >
          {header}
          {children}
        </ScrollView>
      ) : (
        <View style={[styles.readable, { flex: 1, paddingTop: 12 }, pad]}>
          {header}
          {children}
        </View>
      )}
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------- card
export function Card({ children, tone = 'default', style, onPress, accessibilityLabel, accessibilityHint, accessibilityRole = 'button', accessibilityState }: { children: ReactNode; tone?: 'default' | 'alt' | 'warm' | 'primary'; style?: StyleProp<ViewStyle>; onPress?: () => void; accessibilityLabel?: string; accessibilityHint?: string; accessibilityRole?: 'button' | 'radio'; accessibilityState?: { selected?: boolean; checked?: boolean } }) {
  const theme = useTheme();
  const background = { default: theme.colors.surface, alt: theme.colors.alt, warm: theme.colors.warm, primary: theme.colors.primary }[tone];
  const base: StyleProp<ViewStyle> = [styles.card, { backgroundColor: background, borderColor: tone === 'default' ? theme.colors.line : 'transparent' }, style];
  if (!onPress) return <View style={base}>{children}</View>;
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole={accessibilityRole}
      accessibilityState={accessibilityState}
      accessibilityLabel={accessibilityLabel}
      accessibilityHint={accessibilityHint}
      style={({ pressed }) => [base, pressed && { opacity: 0.85 }, pressed && !theme.reduceMotion && styles.pressedCard]}
    >
      {children}
    </Pressable>
  );
}

// -------------------------------------------------------------- button
export type ButtonKind = 'primary' | 'secondary' | 'danger' | 'ghost' | 'again' | 'review' | 'good' | 'easy';

function buttonColors(theme: Theme, kind: ButtonKind): [string, string, string] {
  const c = theme.colors;
  switch (kind) {
    case 'primary':
      return [c.primary, c.onPrimary, c.primaryPressed];
    case 'danger':
      return [c.danger, c.onDanger, c.danger];
    case 'ghost':
      return ['transparent', c.link, c.surfaceSoft];
    case 'again':
    case 'review':
    case 'good':
    case 'easy':
      return [c[kind][0], c[kind][1], c[kind][0]];
    default:
      return [c.surfaceSoft, c.ink, c.alt];
  }
}

export function Button({ label, onPress, kind = 'secondary', icon, disabled, hint, compact, style, sublabel }: { label: string; onPress: () => void; kind?: ButtonKind; icon?: IconName; disabled?: boolean; hint?: string; compact?: boolean; style?: StyleProp<ViewStyle>; sublabel?: string }) {
  const theme = useTheme();
  const [bg, fg, pressedBg] = buttonColors(theme, kind);
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={sublabel ? `${label}, ${sublabel}` : label}
      accessibilityHint={hint}
      accessibilityState={{ disabled: !!disabled }}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: pressed ? pressedBg : bg, minHeight: compact ? 44 : 52, opacity: disabled ? 0.45 : 1 },
        kind === 'secondary' && { borderWidth: StyleSheet.hairlineWidth, borderColor: theme.colors.line },
        // A press answers the moment the finger lands, not on release.
        pressed && !disabled && !theme.reduceMotion && styles.pressedButton,
        style,
      ]}
    >
      {icon ? <Ionicons name={icon} size={theme.font(20)} color={fg} /> : null}
      <View style={{ alignItems: 'center', flexShrink: 1 }}>
        <Text maxFontSizeMultiplier={1.8} style={{ color: fg, fontSize: theme.font(compact ? 15 : 17), fontWeight: '700', textAlign: 'center' }}>{label}</Text>
        {sublabel ? <Text maxFontSizeMultiplier={1.6} style={{ color: fg, fontSize: theme.font(12), opacity: 0.85 }}>{sublabel}</Text> : null}
      </View>
    </Pressable>
  );
}

export function IconButton({ icon, label, onPress }: { icon: IconName; label: string; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      hitSlop={8}
      style={({ pressed }) => [styles.iconButton, { backgroundColor: pressed ? theme.colors.alt : theme.colors.surfaceSoft }]}
    >
      <Ionicons name={icon} size={22} color={theme.colors.ink} />
    </Pressable>
  );
}

// --------------------------------------------------------------- choices
export function Pills<T extends string>({ options, value, onChange, label }: { options: { value: T; label: string }[]; value: T; onChange: (value: T) => void; label?: string }) {
  const theme = useTheme();
  return (
    <View accessibilityRole="radiogroup" accessibilityLabel={label} style={styles.pills}>
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <Pressable
            key={option.value}
            onPress={() => onChange(option.value)}
            accessibilityRole="radio"
            accessibilityState={{ selected, checked: selected }}
            style={({ pressed }) => [
              styles.pill,
              {
                backgroundColor: selected ? theme.colors.primary : pressed ? theme.colors.alt : theme.colors.surface,
                borderColor: selected ? theme.colors.primary : theme.colors.line,
              },
            ]}
          >
            <Text maxFontSizeMultiplier={1.8} style={{ color: selected ? theme.colors.onPrimary : theme.colors.ink, fontWeight: '600', fontSize: theme.font(15) }}>{option.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function Field({ label, hint, ...input }: TextInputProps & { label: string; hint?: string }) {
  const theme = useTheme();
  return (
    <View style={{ gap: 6 }}>
      <Txt variant="h3">{label}</Txt>
      {hint ? <Txt variant="muted">{hint}</Txt> : null}
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor={theme.colors.muted}
        maxFontSizeMultiplier={2}
        {...input}
        style={[
          styles.input,
          {
            backgroundColor: theme.colors.surface,
            borderColor: theme.colors.line,
            color: theme.colors.ink,
            fontSize: theme.font(17),
            minHeight: input.multiline ? 96 : 52,
            textAlignVertical: input.multiline ? 'top' : 'center',
          },
          input.style,
        ]}
      />
    </View>
  );
}

export function ToggleRow({ label, description, value, onChange }: { label: string; description?: string; value: boolean; onChange: (value: boolean) => void }) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={() => onChange(!value)}
      accessibilityRole="switch"
      accessibilityState={{ checked: value }}
      accessibilityLabel={label}
      accessibilityHint={description}
      style={styles.toggle}
    >
      <View style={{ flex: 1, gap: 2 }}>
        <Txt variant="h3">{label}</Txt>
        {description ? <Txt variant="muted">{description}</Txt> : null}
      </View>
      <Switch
        value={value}
        onValueChange={onChange}
        trackColor={{ true: theme.colors.primary, false: theme.colors.line }}
        thumbColor="#ffffff"
        {...({ activeThumbColor: '#ffffff' } as object)}
        importantForAccessibility="no-hide-descendants"
      />
    </Pressable>
  );
}

// ------------------------------------------------------------ progress
export function ProgressBar({ value, color, height = 10, label }: { value: number; color?: string; height?: number; label?: string }) {
  const theme = useTheme();
  const pct = Math.max(0, Math.min(1, value || 0));
  return (
    <View
      accessibilityRole="progressbar"
      accessibilityLabel={label}
      accessibilityValue={{ min: 0, max: 100, now: Math.round(pct * 100) }}
      style={{ height, borderRadius: height, backgroundColor: theme.colors.alt, overflow: 'hidden' }}
    >
      <View style={{ width: `${pct * 100}%`, height: '100%', borderRadius: height, backgroundColor: color ?? theme.colors.primary }} />
    </View>
  );
}

export function Stat({ value, label, color }: { value: string | number; label: string; color?: string }) {
  const theme = useTheme();
  return (
    <View style={{ flex: 1, minWidth: 90 }} accessible accessibilityLabel={`${value} ${label}`}>
      <Txt variant="big" color={color ?? theme.colors.ink}>{String(value)}</Txt>
      <Txt variant="muted">{label}</Txt>
    </View>
  );
}

export function Row({ children, gap = 12, wrap, style }: { children: ReactNode; gap?: number; wrap?: boolean; style?: StyleProp<ViewStyle> }) {
  return <View style={[{ flexDirection: 'row', alignItems: 'center', gap, flexWrap: wrap ? 'wrap' : 'nowrap' }, style]}>{children}</View>;
}

export function SectionTitle({ children, action }: { children: string; action?: ReactNode }) {
  return (
    <Row style={{ justifyContent: 'space-between', marginTop: 8 }}>
      <Txt variant="h2">{children}</Txt>
      {action}
    </Row>
  );
}

export function EmptyState({ icon, title, body, action }: { icon: IconName; title: string; body: string; action?: ReactNode }) {
  const theme = useTheme();
  return (
    <Card style={{ alignItems: 'center', gap: 8, paddingVertical: 28 }}>
      <Ionicons name={icon} size={36} color={theme.colors.muted} />
      <Txt variant="h3" center>{title}</Txt>
      <Txt variant="muted" center>{body}</Txt>
      {action}
    </Card>
  );
}

export function Icon({ name, size = 22, color }: { name: IconName; size?: number; color?: string }) {
  const theme = useTheme();
  return <Ionicons name={name} size={theme.font(size)} color={color ?? theme.colors.ink} />;
}

const styles = StyleSheet.create({
  readable: { width: '100%', maxWidth: READABLE_WIDTH, alignSelf: 'center' },
  pressedCard: { transform: [{ scale: 0.98 }] },
  pressedButton: { transform: [{ scale: 0.97 }] },
  header: { flexDirection: 'row', alignItems: 'flex-end', gap: 12, marginBottom: 4 },
  card: { borderRadius: 18, padding: 18, gap: 10, borderWidth: StyleSheet.hairlineWidth },
  button: { borderRadius: 14, paddingHorizontal: 18, paddingVertical: 10, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10 },
  iconButton: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  pills: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  pill: { minHeight: 44, minWidth: 56, paddingHorizontal: 16, borderRadius: 22, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  input: { borderWidth: 1, borderRadius: 14, paddingHorizontal: 14, paddingVertical: 12 },
  toggle: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56, paddingVertical: 6 },
});
