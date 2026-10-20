/** What Google Drive sync tells people when something goes wrong (as in drive.py's MESSAGES). */
import { CloudError } from './client';

const MESSAGES: Record<string, string> = {
  drive_signed_out: 'Google Drive was disconnected. Connect it again in Account & sync to keep syncing.',
  drive_scope: 'MemoryPal needs permission to keep its sync file in your Google Drive. Connect again and leave the Google Drive box ticked.',
  drive_full: "Your Google Drive is full, so MemoryPal can't save your cards there. Free up space in Google Drive, then sync again.",
  drive_busy: 'Google Drive is busy right now. MemoryPal will try again in a few minutes.',
  drive_offline: "Couldn't reach Google Drive. Check the internet connection and try again.",
  drive_cancelled: "Google Drive wasn't connected. Try again when you're ready.",
  drive_not_linked: 'Connect Google Drive in Account & sync to sync your cards.',
  drive_no_play_services: 'Connecting Google Drive needs Google Play services on this phone.',
};

export function driveError(code: string): CloudError {
  return new CloudError(MESSAGES[code] ?? MESSAGES.drive_busy, code);
}
