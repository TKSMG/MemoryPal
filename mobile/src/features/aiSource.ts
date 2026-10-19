/**
 * Choosing what the AI reads: a PDF (document picker) or a photo (camera or
 * photo library), read as base64 for the request. Picked files stay in the
 * cache until the person saves cards or notes made from them; then a copy is
 * kept in the app's documents folder so the cards can show it later.
 */
import * as DocumentPicker from 'expo-document-picker';
import { Directory, File, Paths } from 'expo-file-system';
import * as ImagePicker from 'expo-image-picker';

import { uid } from '../core/models';

export interface AiSource {
  kind: 'pdf' | 'image';
  name: string;
  mime: string;
  base64: string;
  /** Where the picked file is now (cache or picker URI). */
  uri: string;
}

export type PickResult = { source: AiSource } | { cancelled: true } | { denied: string };

export async function pickPdf(): Promise<PickResult> {
  const result = await DocumentPicker.getDocumentAsync({ type: 'application/pdf', copyToCacheDirectory: true });
  if (result.canceled || !result.assets?.length) return { cancelled: true };
  const asset = result.assets[0];
  const base64 = await new File(asset.uri).base64();
  return { source: { kind: 'pdf', name: asset.name || 'Document.pdf', mime: 'application/pdf', base64, uri: asset.uri } };
}

export async function pickPhoto(from: 'camera' | 'library'): Promise<PickResult> {
  if (from === 'camera') {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) return { denied: 'Camera access is off. You can allow it in the phone’s Settings, or choose a photo instead.' };
  }
  // The photo library uses the system picker, which needs no permission.
  const options: ImagePicker.ImagePickerOptions = { mediaTypes: ['images'], base64: true, quality: 0.7, allowsEditing: false };
  const result = from === 'camera' ? await ImagePicker.launchCameraAsync(options) : await ImagePicker.launchImageLibraryAsync(options);
  if (result.canceled || !result.assets?.length) return { cancelled: true };
  const asset = result.assets[0];
  const base64 = asset.base64 || (await new File(asset.uri).base64());
  // With quality below 1 the picker hands back a JPEG.
  return { source: { kind: 'image', name: asset.fileName || 'Photo.jpg', mime: asset.mimeType || 'image/jpeg', base64, uri: asset.uri } };
}

/** Keeps a copy of the source in the app's documents; its file:// URI, or '' if it couldn't be kept. */
export async function keepSource(source: AiSource): Promise<string> {
  try {
    const folder = new Directory(Paths.document, 'ai-sources');
    if (!folder.exists) folder.create({ intermediates: true, idempotent: true });
    const extension = source.kind === 'pdf' ? 'pdf' : source.mime === 'image/png' ? 'png' : 'jpg';
    const target = new File(folder, `${uid()}.${extension}`);
    await new File(source.uri).copy(target);
    return target.uri;
  } catch {
    return '';
  }
}
