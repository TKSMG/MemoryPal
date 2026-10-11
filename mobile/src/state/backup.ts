/** Save or open a backup file (the same JSON the desktop app exports and imports). */
import * as DocumentPicker from 'expo-document-picker';
import { File, Paths } from 'expo-file-system';
import * as Sharing from 'expo-sharing';

import { todayIso } from '../core/dates';

export function backupName(): string {
  return `memorypal-backup-${todayIso()}.json`;
}

/** Hand the backup to the share sheet (Files, Drive, email…). */
export async function exportBackup(text: string): Promise<void> {
  const file = new File(Paths.cache, backupName());
  if (file.exists) file.delete();
  file.create();
  file.write(text);
  await Sharing.shareAsync(file.uri, { mimeType: 'application/json', dialogTitle: 'Save your MemoryPal backup', UTI: 'public.json' });
}

/** Let the person pick a backup file; returns its text, or null if they cancel. */
export async function pickBackup(): Promise<string | null> {
  const result = await DocumentPicker.getDocumentAsync({ type: ['application/json', 'text/plain', '*/*'], copyToCacheDirectory: true });
  if (result.canceled || !result.assets?.length) return null;
  return new File(result.assets[0].uri).text();
}
