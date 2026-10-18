/** Building blocks shared by every screen: calm, large, and accessible by default. */
import Ionicons from '@expo/vector-icons/Ionicons';
import { ReactElement, ReactNode, Ref, useRef, useState } from 'react';
import {
  FlatList,
  KeyboardAvoidingView,
  ListRenderItem,
  Platform,
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

import { pressedShade, Theme, useTheme } from './theme';

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

export function Txt({ variant = 'body', color, style, children, center, ...rest }: { variant?: Variant; color?: string; style?: StyleProp<TextStyle>; children: ReactNode; center?: boolean; numberOfLines?: number; adjustsFontSizeToFit?: boolean; maxFontSizeMultiplier?: number; accessibilityRole?: 'header' | 'text'; accessibilityLabel?: string; accessibilityLiveRegion?: 'none' | 'polite' | 'assertive' }) {
  const theme = useTheme();
  const [size, weight, line] = SIZES[variant];
  // Big headings grow less than body text with the in-app text size, so a
  // page title still fits on one line on a small phone.
  const grow = variant === 'title' || variant === 'big' ? Math.min(theme.scale, 1.1) / theme.scale : 1;
  const tone = color ?? (variant === 'muted' || variant === 'small' || variant === 'label' ? theme.colors.muted : theme.colors.ink);
  return (
    <Text
      maxFontSizeMultiplier={rest.maxFontSizeMultiplier ?? 2}
      adjustsFontSizeToFit={rest.adjustsFontSizeToFit}
      accessibilityLabel={rest.accessibilityLabel}
      accessibilityLiveRegion={rest.accessibilityLiveRegion}
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
/** Forms (sign-in, add, edit) stop at a narrower width so fields don't stretch across an iPad. */
const FORM_WIDTH = 520;

/** Side margins follow the screen: tighter on small phones so nothing is
 * squeezed, roomier on tablets (where content also stops at a readable width). */
function useGutter(): number {
  const { width } = useWindowDimensions();
  return width < 360 ? 16 : width >= 600 ? 28 : 20;
}

function ScreenHeader({ title, eyebrow, right }: { title?: string; eyebrow?: string; right?: ReactNode }) {
  const theme = useTheme();
  if (!title) return null;
  return (
    <View style={styles.header}>
      <View style={{ flex: 1 }}>
        {eyebrow ? <Txt variant="label" color={theme.colors.link}>{eyebrow}</Txt> : null}
        <Txt variant="title">{title}</Txt>
      </View>
      {right}
    </View>
  );
}

export function Screen({ title, eyebrow, right, children, scroll = true, padded = true, narrow }: { title?: string; eyebrow?: string; right?: ReactNode; children: ReactNode; scroll?: boolean; padded?: boolean; /** Cap the content at form width (centred) on wide screens. */ narrow?: boolean }) {
  const theme = useTheme();
  const header = <ScreenHeader title={title} eyebrow={eyebrow} right={right} />;
  const gutter = useGutter();
  const pad = padded ? { paddingHorizontal: gutter } : null;
  const width = narrow ? { maxWidth: FORM_WIDTH + (padded ? gutter * 2 : 0) } : null;
  // iOS scroll views move clear of the keyboard on their own
  // (automaticallyAdjustKeyboardInsets); Android, drawn edge to edge, needs a
  // keyboard-avoiding view, offset by however far the screen sits below the
  // top of the window (the navigation bar, when there is one).
  const frameRef = useRef<View>(null);
  const [topOffset, setTopOffset] = useState(0);
  const measureTop = () => {
    if (Platform.OS !== 'android') return;
    frameRef.current?.measureInWindow((_x, y) => setTopOffset(Math.max(0, Math.round(y))));
  };
  // The native safe area view pads only where the screen really meets the
  // status bar or home indicator, so screens under a navigation bar or above
  // the tab bar get no extra gap.
  return (
    <SafeAreaView ref={frameRef} onLayout={measureTop} edges={['top', 'bottom', 'left', 'right']} style={{ flex: 1, backgroundColor: theme.colors.bg }}>
      {scroll ? (
        <KeyboardAvoidingView style={{ flex: 1 }} enabled={Platform.OS === 'android'} behavior="padding" keyboardVerticalOffset={topOffset}>
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={[styles.readable, { paddingTop: 12, paddingBottom: 32, gap: 16 }, pad, width]}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="interactive"
          automaticallyAdjustKeyboardInsets
        >
          {header}
          {children}
        </ScrollView>
        </KeyboardAvoidingView>
      ) : (
        <View style={[styles.readable, { flex: 1, paddingTop: 12 }, pad, width]}>
          {header}
          {children}
        </View>
      )}
    </SafeAreaView>
  );
}

/**
 * A screen whose body is a long list: rows are virtualised (only those near
 * the viewport are rendered), and the header content scrolls with them. The
 * list spans the whole width so a drag in the iPad side margins still scrolls.
 */
export function ScreenList<T>({ title, eyebrow, right, header, data, renderItem, keyExtractor, empty }: { title?: string; eyebrow?: string; right?: ReactNode; header?: ReactNode; data: readonly T[]; renderItem: ListRenderItem<T>; keyExtractor: (item: T) => string; empty?: ReactElement | null }) {
  const theme = useTheme();
  const gutter = useGutter();
  const column = [styles.readable, { paddingHorizontal: gutter }];
  return (
    <SafeAreaView edges={['top', 'bottom', 'left', 'right']} style={{ flex: 1, backgroundColor: theme.colors.bg }}>
      <FlatList
        style={{ flex: 1 }}
        data={data}
        renderItem={(info) => <View style={column}>{renderItem(info)}</View>}
        keyExtractor={keyExtractor}
        contentContainerStyle={{ paddingTop: 12, paddingBottom: 32 }}
        ListHeaderComponent={
          <View style={[column, { gap: 16, marginBottom: 16 }]}>
            <ScreenHeader title={title} eyebrow={eyebrow} right={right} />
            {header}
          </View>
        }
        ListEmptyComponent={empty ? <View style={column}>{empty}</View> : null}
        ItemSeparatorComponent={ListGap}
        initialNumToRender={8}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        automaticallyAdjustKeyboardInsets
      />
    </SafeAreaView>
  );
}

function ListGap() {
  return <View style={{ height: 16 }} />;
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
      // A short delay keeps the pressed look off cards a finger only lands
      // on to start scrolling.
      unstable_pressDelay={80}
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
/** Smallest touch target: Apple asks for 44pt, Android's Material guidance for 48dp. */
const MIN_TOUCH = Platform.OS === 'android' ? 48 : 44;

export type ButtonKind = 'primary' | 'secondary' | 'danger' | 'dangerGhost' | 'ghost' | 'again' | 'review' | 'good' | 'easy';

function buttonColors(theme: Theme, kind: ButtonKind): [string, string, string] {
  const c = theme.colors;
  switch (kind) {
    case 'primary':
      return [c.primary, c.onPrimary, c.primaryPressed];
    case 'danger':
      return [c.danger, c.onDanger, c.dangerPressed];
    case 'ghost':
      return ['transparent', c.link, c.surfaceSoft];
    case 'dangerGhost':
      return ['transparent', c.dangerText, c.surfaceSoft];
    case 'again':
    case 'review':
    case 'good':
    case 'easy':
      return [c[kind][0], c[kind][1], pressedShade(c[kind][0], theme.dark)];
    default:
      return [c.surfaceSoft, c.ink, c.alt];
  }
}

export function Button({ label, onPress, kind = 'secondary', icon, disabled, hint, compact, inline, style, sublabel, accessibilityLabel }: { label: string; onPress: () => void; kind?: ButtonKind; icon?: IconName; disabled?: boolean; hint?: string; compact?: boolean; /** Text-only ghost action that lines its text up with the content edge (e.g. a section title's action); the hit area grows outward instead. */ inline?: boolean; style?: StyleProp<ViewStyle>; sublabel?: string; accessibilityLabel?: string }) {
  const theme = useTheme();
  const [bg, fg, pressedBg] = buttonColors(theme, kind);
  return (
    <Pressable
      onPress={onPress}
      hitSlop={inline ? { left: 8, right: 8 } : undefined}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? (sublabel ? `${label}, ${sublabel}` : label)}
      accessibilityHint={hint}
      accessibilityState={{ disabled: !!disabled }}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: pressed ? pressedBg : bg, minHeight: compact ? MIN_TOUCH : 52, opacity: disabled ? 0.45 : 1 },
        kind === 'secondary' && { borderWidth: StyleSheet.hairlineWidth, borderColor: theme.colors.line },
        inline && styles.inlineButton,
        // A press answers the moment the finger lands, not on release.
        pressed && !disabled && !theme.reduceMotion && styles.pressedButton,
        style,
      ]}
    >
      {icon ? <Ionicons name={icon} size={theme.font(20)} color={fg} /> : null}
      <View style={{ alignItems: 'center', flexShrink: 1 }}>
        <Text maxFontSizeMultiplier={1.8} style={{ color: fg, fontSize: theme.font(compact ? 15 : 17), fontWeight: '700', textAlign: 'center' }}>{label}</Text>
        {sublabel ? <Text maxFontSizeMultiplier={1.6} style={{ color: fg, fontSize: theme.font(12), fontWeight: '500' }}>{sublabel}</Text> : null}
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
      <Ionicons name={icon} size={theme.icon(22)} color={theme.colors.ink} />
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

export function Field({ label, hint, ref, ...input }: TextInputProps & { label: string; hint?: string; ref?: Ref<TextInput> }) {
  const theme = useTheme();
  const [focused, setFocused] = useState(false);
  return (
    <View style={{ gap: 6 }}>
      <Txt variant="h3">{label}</Txt>
      {hint ? <Txt variant="muted">{hint}</Txt> : null}
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor={theme.colors.muted}
        maxFontSizeMultiplier={2}
        {...input}
        ref={ref}
        onFocus={(event) => {
          setFocused(true);
          input.onFocus?.(event);
        }}
        onBlur={(event) => {
          setFocused(false);
          input.onBlur?.(event);
        }}
        style={[
          styles.input,
          // Focus thickens the outline to 2pt in the primary colour; the
          // padding gives back the extra point so the text doesn't shift.
          focused && styles.inputFocused,
          {
            backgroundColor: theme.colors.surface,
            borderColor: focused ? theme.colors.primary : theme.colors.inputBorder,
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
      android_ripple={Platform.OS === 'android' ? { color: theme.colors.alt } : undefined}
      style={({ pressed }) => [styles.toggle, pressed && Platform.OS !== 'android' && { backgroundColor: theme.colors.surfaceSoft }]}
    >
      <View style={{ flex: 1, gap: 2 }}>
        <Txt variant="h3">{label}</Txt>
        {description ? <Txt variant="muted">{description}</Txt> : null}
      </View>
      <Switch
        value={value}
        onValueChange={onChange}
        trackColor={{ true: theme.colors.primary, false: theme.colors.muted }}
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
      <Ionicons name={icon} size={theme.icon(36)} color={theme.colors.muted} />
      <Txt variant="h3" center>{title}</Txt>
      <Txt variant="muted" center>{body}</Txt>
      {action}
    </Card>
  );
}

// ------------------------------------------------------------ grouped list
/**
 * An inset grouped list, like iOS Settings: one rounded surface, rows split by
 * hairlines indented past the icon. Replaces a stack of separate bordered cards.
 */
export function ListGroup({ children, header, footer }: { children: ReactNode; header?: string; footer?: string }) {
  const theme = useTheme();
  const items = (Array.isArray(children) ? children.flat() : [children]).filter(Boolean);
  return (
    <View style={{ gap: 8 }}>
      {header ? <Txt variant="h3" accessibilityRole="header" style={{ marginTop: 8 }}>{header}</Txt> : null}
      <View style={[styles.group, { backgroundColor: theme.colors.surface }]}>
        {items.map((child, i) => (
          <View key={i}>
            {i ? <View style={[styles.separator, { backgroundColor: theme.colors.line }]} /> : null}
            {child}
          </View>
        ))}
      </View>
      {footer ? <Txt variant="small" style={{ paddingHorizontal: 4 }}>{footer}</Txt> : null}
    </View>
  );
}

/** One row of a ListGroup: icon, title, optional detail and value, and a chevron when it opens something. */
export function ListRow({ icon, title, detail, value, onPress, accessibilityLabel, accessibilityHint, tint, right, chevron = !!onPress }: { icon?: IconName; title: string; detail?: string; value?: string; onPress?: () => void; accessibilityLabel?: string; accessibilityHint?: string; tint?: string; right?: ReactNode; chevron?: boolean }) {
  const theme = useTheme();
  const c = theme.colors;
  const body = (
    <>
      {icon ? <Ionicons name={icon} size={theme.icon(22)} color={tint ?? c.primary} style={{ width: theme.icon(26) }} /> : null}
      <View style={{ flex: 1, gap: 2, paddingVertical: 2 }}>
        <Txt variant="body" color={tint && !icon ? tint : c.ink} style={{ fontWeight: '500' }}>{title}</Txt>
        {detail ? <Txt variant="small">{detail}</Txt> : null}
      </View>
      {value ? <Txt variant="muted">{value}</Txt> : null}
      {right}
      {chevron ? <Ionicons name="chevron-forward" size={theme.icon(18)} color={c.muted} /> : null}
    </>
  );
  if (!onPress) {
    return <View style={styles.listRow} accessible accessibilityLabel={accessibilityLabel}>{body}</View>;
  }
  return (
    <Pressable
      onPress={onPress}
      unstable_pressDelay={60}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? [title, detail, value].filter(Boolean).join(', ')}
      accessibilityHint={accessibilityHint}
      android_ripple={Platform.OS === 'android' ? { color: c.alt } : undefined}
      style={({ pressed }) => [styles.listRow, pressed && Platform.OS !== 'android' && { backgroundColor: c.surfaceSoft }]}
    >
      {body}
    </Pressable>
  );
}

/** A heading that shows or hides what's under it, for options most people don't need. */
export function Disclosure({ title, open, onToggle, children, summary }: { title: string; open: boolean; onToggle: () => void; children: ReactNode; summary?: string }) {
  const theme = useTheme();
  return (
    <View style={{ gap: 12 }}>
      <Pressable
        onPress={onToggle}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel={summary ? `${title}, ${summary}` : title}
        style={({ pressed }) => [styles.disclosure, pressed && { opacity: 0.6 }]}
      >
        <Txt variant="h3" color={theme.colors.link} style={{ flex: 1 }}>{title}</Txt>
        {summary && !open ? <Txt variant="muted">{summary}</Txt> : null}
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={theme.icon(18)} color={theme.colors.link} />
      </Pressable>
      {open ? children : null}
    </View>
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
  pill: { minHeight: MIN_TOUCH, minWidth: 56, paddingHorizontal: 16, borderRadius: 22, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  inlineButton: { paddingHorizontal: 6, marginHorizontal: -6 },
  input: { borderWidth: 1, borderRadius: 14, paddingHorizontal: 14, paddingVertical: 12 },
  // The primary border is the focus ring, so the browser's own outline is dropped on web.
  inputFocused: { borderWidth: 2, paddingHorizontal: 13, paddingVertical: 11, ...(Platform.OS === 'web' ? ({ outlineStyle: 'none' } as unknown as TextStyle) : null) },
  // The pressed highlight reaches a little past the text, so the row reads as one target.
  group: { borderRadius: 14, overflow: 'hidden' },
  separator: { height: StyleSheet.hairlineWidth, marginLeft: 16 },
  listRow: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 52, paddingHorizontal: 16, paddingVertical: 10 },
  disclosure: { flexDirection: 'row', alignItems: 'center', gap: 8, minHeight: MIN_TOUCH },
  toggle: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56, paddingVertical: 6, paddingHorizontal: 8, marginHorizontal: -8, borderRadius: 12, overflow: 'hidden' },
});
