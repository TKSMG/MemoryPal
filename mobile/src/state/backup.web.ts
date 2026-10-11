/** Browser version: download the backup, and read a chosen file. */
import * as DocumentPicker from 'expo-document-picker';

import { todayIso } from '../core/dates';

export function backupName(): string {
  return `memorypal-backup-${todayIso()}.json`;
}

export async function exportBackup(text: string): Promise<void> {
  const url = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = backupName();
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function pickBackup(): Promise<string | null> {
  const result = await DocumentPicker.getDocumentAsync({ type: ['application/json', 'text/plain'] });
  if (result.canceled || !result.assets?.length) return null;
  const asset = result.assets[0];
  return asset.file ? asset.file.text() : (await fetch(asset.uri)).text();
}
