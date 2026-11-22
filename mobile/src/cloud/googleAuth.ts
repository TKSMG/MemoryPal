/**
 * Connecting the person's Google account for Drive sync (phones only).
 *
 * Google's own sign-in on the phone keeps the connection and hands out
 * fresh access tokens, so MemoryPal never stores a Google token itself. The
 * only permission asked for is drive.appdata: a hidden folder in the
 * person's Drive that only MemoryPal can see.
 */
import Constants from 'expo-constants';
import { Platform } from 'react-native';

import { CloudError } from './client';
import { driveError } from './driveErrors';

export const DRIVE_SCOPE = 'https://www.googleapis.com/auth/drive.appdata';

type Native = typeof import('@react-native-google-signin/google-signin');

/**
 * The native sign-in module, loaded on first use: a build without it (Expo
 * Go, tests, a build without Drive sync) must still start.
 */
function native(): Native {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  return require('@react-native-google-signin/google-signin') as Native;
}

/** The iOS OAuth client id from app.config.js; empty means Drive sync isn't set up in this build. */
function iosClientId(): string {
  const extra = (Constants.expoConfig?.extra ?? {}) as Record<string, unknown>;
  const drive = (extra.googleDrive ?? {}) as Record<string, unknown>;
  return typeof drive.iosClientId === 'string' ? drive.iosClientId.trim() : '';
}

export function googleConfigured(): boolean {
  return Boolean(iosClientId());
}

let ready = false;

function setup(): Native {
  const module = native();
  if (!ready) {
    module.GoogleSignin.configure({ scopes: [DRIVE_SCOPE], iosClientId: iosClientId() });
    ready = true;
  }
  return module;
}

const code = (error: unknown) => String((error as { code?: unknown } | null)?.code ?? '');

/** Ask the person to pick a Google account and allow the Drive folder: { user_id, email }. */
export async function connectGoogle(): Promise<{ user_id: string; email: string }> {
  let module: Native;
  try {
    module = setup();
  } catch {
    throw driveError('drive_not_linked');
  }
  const { GoogleSignin, statusCodes } = module;
  try {
    if (Platform.OS === 'android') await GoogleSignin.hasPlayServices({ showPlayServicesUpdateDialog: true });
    const result = await GoogleSignin.signIn();
    if (result.type !== 'success') throw driveError('drive_cancelled');
    if (!result.data.scopes.includes(DRIVE_SCOPE)) {
      const added = await GoogleSignin.addScopes({ scopes: [DRIVE_SCOPE] });
      if (!added || added.type !== 'success' || !added.data.scopes.includes(DRIVE_SCOPE)) throw driveError('drive_scope');
    }
    return { user_id: result.data.user.id, email: result.data.user.email };
  } catch (error) {
    if (error instanceof CloudError) throw error;
    if (code(error) === statusCodes.SIGN_IN_CANCELLED) throw driveError('drive_cancelled');
    if (code(error) === statusCodes.PLAY_SERVICES_NOT_AVAILABLE) throw driveError('drive_no_play_services');
    // Android: 10 (DEVELOPER_ERROR) and 12500 (SIGN_IN_FAILED) mean Google doesn't
    // know this copy of the app: its signing certificate isn't on MemoryPal's
    // Android OAuth client (a sideloaded APK is signed with the upload key, the
    // Play Store copy with Google's app-signing key; both need a client).
    if (SETUP_CODES.includes(code(error))) throw driveError('drive_setup');
    throw driveError('drive_offline');
  }
}

const SETUP_CODES = ['10', '12500', 'DEVELOPER_ERROR'];

let lastToken = '';

/** A Drive access token; `renew` drops the cached one first (after a 401). */
export async function googleAccessToken(renew = false): Promise<string> {
  let module: Native;
  try {
    module = setup();
  } catch {
    throw driveError('drive_signed_out');
  }
  const { GoogleSignin, statusCodes } = module;
  try {
    if (renew && lastToken) await GoogleSignin.clearCachedAccessToken(lastToken);
    if (!GoogleSignin.getCurrentUser()) {
      const silent = await GoogleSignin.signInSilently();
      if (silent.type !== 'success') throw driveError('drive_signed_out');
    }
    lastToken = (await GoogleSignin.getTokens()).accessToken;
    return lastToken;
  } catch (error) {
    if (error instanceof CloudError) throw error;
    if (code(error) === statusCodes.SIGN_IN_REQUIRED) throw driveError('drive_signed_out');
    throw driveError('drive_offline');
  }
}

/** Take back MemoryPal's access and forget the Google account on this phone. */
export async function disconnectGoogle() {
  let GoogleSignin: Native['GoogleSignin'];
  try {
    GoogleSignin = setup().GoogleSignin;
  } catch {
    return;
  }
  try {
    await GoogleSignin.revokeAccess();
  } catch {
    // offline, or already revoked: forgetting it here still works
  }
  try {
    await GoogleSignin.signOut();
  } catch {
    // nothing left to sign out of
  }
}
