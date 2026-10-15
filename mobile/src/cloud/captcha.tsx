/**
 * The CAPTCHA check before signing in, creating an account or emailing a
 * code. Turnstile doesn't run natively, so the check page (site/verify/)
 * opens in a sheet with a web view and posts the token back.
 */
import { ReactNode, useCallback, useRef, useState } from 'react';
import { Modal, View } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { WebView } from 'react-native-webview';
import type { ShouldStartLoadRequest, WebViewMessageEvent } from 'react-native-webview/lib/WebViewTypes';

import { Button, Txt } from '../ui/components';
import { useTheme } from '../ui/theme';
import { allowedInCheck, readCheckMessage } from './checkPage';
import { captchaUrl, CloudError } from './client';

const FAILED = "The quick check that keeps out bots didn't work. Try again.";
const CANCELLED = "The quick check was closed before it finished. Try again when you're ready.";

/** `request` resolves with a token once the person passes the check; render `sheet` on the screen. */
export function useCaptcha(): { request?: () => Promise<string>; sheet: ReactNode } {
  const theme = useTheme();
  const page = captchaUrl();
  const [open, setOpen] = useState(false);
  const pending = useRef<{ resolve: (token: string) => void; reject: (error: Error) => void } | null>(null);

  const finish = useCallback((token?: string, error?: CloudError) => {
    const waiting = pending.current;
    pending.current = null;
    setOpen(false);
    if (!waiting) return;
    if (token) waiting.resolve(token);
    else waiting.reject(error ?? new CloudError(FAILED, 'captcha_failed'));
  }, []);

  const request = useCallback(() => new Promise<string>((resolve, reject) => {
    pending.current?.reject(new CloudError(CANCELLED, 'captcha_cancelled'));
    pending.current = { resolve, reject };
    setOpen(true);
  }), []);

  const onMessage = (event: WebViewMessageEvent) => {
    if (!event.nativeEvent.url.startsWith(page)) return;
    const message = readCheckMessage(event.nativeEvent.data);
    if (message?.token) finish(message.token);
    else if (message) finish(undefined, new CloudError(FAILED, 'captcha_failed'));
  };

  const cancel = () => finish(undefined, new CloudError(CANCELLED, 'captcha_cancelled'));

  if (!page) return { request: undefined, sheet: null };
  const sheet = (
    <Modal visible={open} animationType="slide" presentationStyle="pageSheet" onRequestClose={cancel}>
      <SafeAreaProvider>
        <SafeAreaView edges={['top', 'bottom', 'left', 'right']} style={{ flex: 1, backgroundColor: theme.colors.bg }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: theme.colors.line }}>
            <Txt variant="h3" accessibilityRole="header">Quick check</Txt>
            <Button label="Cancel" kind="ghost" compact onPress={cancel} />
          </View>
          {open ? (
            <WebView
              source={{ uri: page }}
              style={{ flex: 1, backgroundColor: theme.colors.bg }}
              originWhitelist={['https://*', 'about:blank', 'about:srcdoc']}
              onShouldStartLoadWithRequest={(request: ShouldStartLoadRequest) => request.isTopFrame === false || allowedInCheck(request.url, page)}
              javaScriptEnabled
              domStorageEnabled
              setSupportMultipleWindows={false}
              onMessage={onMessage}
              onError={() => finish(undefined, new CloudError("Couldn't load the quick check. Check the internet connection and try again.", 'offline'))}
              onHttpError={(event) => {
                if (event.nativeEvent.url.startsWith(page)) finish(undefined, new CloudError(FAILED, 'captcha_failed'));
              }}
            />
          ) : null}
        </SafeAreaView>
      </SafeAreaProvider>
    </Modal>
  );
  return { request, sheet };
}
