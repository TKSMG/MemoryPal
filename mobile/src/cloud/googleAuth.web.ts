/** Drive sync is for the phone apps; the web build keeps syncing through the MemoryPal cloud. */
import { driveError } from './driveErrors';

export const DRIVE_SCOPE = 'https://www.googleapis.com/auth/drive.appdata';

export function googleConfigured(): boolean {
  return false;
}

export async function connectGoogle(): Promise<{ user_id: string; email: string }> {
  throw driveError('drive_not_linked');
}

export async function googleAccessToken(): Promise<string> {
  throw driveError('drive_signed_out');
}

export async function disconnectGoogle() {}
