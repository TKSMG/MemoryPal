/** Browser version: pick a PDF or picture file; nothing is kept (there's no app folder). */
import * as DocumentPicker from 'expo-document-picker';

export interface AiSource {
  kind: 'pdf' | 'image';
  name: string;
  mime: string;
  base64: string;
  uri: string;
}

export type PickResult = { source: AiSource } | { cancelled: true } | { denied: string };

function readBase64(file: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? '').replace(/^data:[^,]*,/, ''));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function pick(type: string[], kind: AiSource['kind']): Promise<PickResult> {
  const result = await DocumentPicker.getDocumentAsync({ type });
  if (result.canceled || !result.assets?.length) return { cancelled: true };
  const asset = result.assets[0];
  const blob = asset.file ?? (await (await fetch(asset.uri)).blob());
  const mime = asset.mimeType || blob.type || (kind === 'pdf' ? 'application/pdf' : 'image/jpeg');
  return { source: { kind, name: asset.name, mime, base64: await readBase64(blob), uri: '' } };
}

export function pickPdf(): Promise<PickResult> {
  return pick(['application/pdf'], 'pdf');
}

export function pickPhoto(_from: 'camera' | 'library'): Promise<PickResult> {
  return pick(['image/png', 'image/jpeg', 'image/webp', 'image/heic'], 'image');
}

export async function keepSource(_source: AiSource): Promise<string> {
  return '';
}
