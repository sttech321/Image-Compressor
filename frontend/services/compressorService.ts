const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000'
).replace(/\/$/, '');

function toApiUrl(pathOrUrl: string): string {
  try {
    return new URL(pathOrUrl).toString();
  } catch {
    const path = pathOrUrl.startsWith('/') ? pathOrUrl : `/${pathOrUrl}`;
    return `${API_BASE_URL}${path}`;
  }
}

export interface CompressionResponse {
  status: string;
  message: string;
  archive: string;
  size_mb: number;
  download_url: string;
  original_size_mb?: number;
}

function getUploadFilename(file: File): string {
  return file.webkitRelativePath || file.name;
}

export type ImageDownloadFormat = 'original' | 'png' | 'jpeg' | 'webp';

export interface DecompressedFile {
  name: string;
  path: string;
  size: number;
  size_mb: number;
  url: string;
  preview_url: string;
}

export interface DecompressionResponse {
  status: string;
  message: string;
  files: DecompressedFile[];
  count: number;
  output_folder: string;
  download_all_url: string;
  image_format: ImageDownloadFormat;
}

export async function compressImages(
  files: File[],
  quality: string,
  lossless: boolean,
  format: 'dcv' | 'zip' = 'dcv'
): Promise<CompressionResponse> {
  const formData = new FormData();

  files.forEach((file) => {
    formData.append('files', file, getUploadFilename(file));
  });

  formData.append('quality', quality);
  formData.append('lossless', lossless.toString());
  formData.append('format', format);

  const response = await fetch(`${API_BASE_URL}/api/compress`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.details || error.error || 'Compression failed');
  }

  const data: CompressionResponse = await response.json();

  return {
    ...data,
    download_url: toApiUrl(data.download_url || `/api/download/${data.archive}`),
  };
}

export async function decompressArchive(
  file: File,
  imageFormat: ImageDownloadFormat = 'original'
): Promise<DecompressionResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('image_format', imageFormat);

  const response = await fetch(`${API_BASE_URL}/api/decompress`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.details || error.error || 'Decompression failed');
  }

  const data: DecompressionResponse = await response.json();

  return {
    ...data,
    download_all_url: toApiUrl(
      data.download_all_url || `/api/download-folder/${data.output_folder}`
    ),
    files: data.files.map((file) => ({
      ...file,
      url: toApiUrl(file.url),
      preview_url: toApiUrl(file.preview_url),
    })),
  };
}

export function getDownloadUrl(filename: string): string {
  return toApiUrl(`/api/download/${encodeURIComponent(filename)}`);
}
