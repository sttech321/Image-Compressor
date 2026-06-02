'use client';

/* eslint-disable @next/next/no-img-element */

import type {
  CompressionResponse,
  DecompressionResponse,
} from '@/services/compressorService';

interface ResultsDisplayProps {
  compressionResult?: CompressionResponse | null;
  decompressedResult?: DecompressionResponse | null;
  onNewCompression: () => void;
  originalSize?: number;
}

export default function ResultsDisplay({
  compressionResult,
  decompressedResult,
  onNewCompression,
  originalSize = 0,
}: ResultsDisplayProps) {
  if (compressionResult) {
    return (
      <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-8 backdrop-blur">
        <div className="mb-8 text-center">
          <p className="mb-2 text-sm font-bold uppercase tracking-wide text-green-400">
            Ready
          </p>
          <h2 className="mb-2 text-3xl font-bold text-white">Success!</h2>
          <p className="text-slate-300">Your images have been compressed</p>
        </div>

        <div className="mb-6 sm:mb-8 grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-3 md:gap-6">
          <div className="rounded-lg border border-slate-700 bg-slate-900/50 p-3 sm:p-4 md:p-6 text-center">
            <p className="mb-1 sm:mb-2 text-xs sm:text-sm text-slate-400">Original Size</p>
            <p className="text-sm sm:text-base md:text-lg font-bold text-white">
              {originalSize > 0 ? (originalSize / (1024 * 1024)).toFixed(2) : 'N/A'} MB
            </p>
          </div>
          <div className="rounded-lg border border-slate-700 bg-slate-900/50 p-3 sm:p-4 md:p-6 text-center">
            <p className="mb-1 sm:mb-2 text-xs sm:text-sm text-slate-400">Compressed Size</p>
            <p className="text-sm sm:text-base md:text-lg font-bold text-white">
              {compressionResult.size_mb} MB
            </p>
          </div>
          <div className="rounded-lg border border-slate-700 bg-slate-900/50 p-3 sm:p-4 md:p-6 text-center">
            <p className="mb-1 sm:mb-2 text-xs sm:text-sm text-slate-400">Space Saved</p>
            <p className="text-sm sm:text-base md:text-lg font-bold text-green-400">
              {originalSize > 0 ? ((1 - compressionResult.size_mb * 1024 * 1024 / originalSize) * 100).toFixed(1) : 'N/A'}%
            </p>
          </div>
          <div className="rounded-lg border border-slate-700 bg-slate-900/50 p-3 sm:p-4 md:p-6 text-center">
            <p className="mb-1 sm:mb-2 text-xs sm:text-sm text-slate-400">Status</p>
            <p className="text-sm sm:text-base md:text-lg font-bold text-green-400">Ready ✓</p>
          </div>
        </div>

        <div className="mb-6 sm:mb-8 rounded-lg border border-slate-700 bg-slate-900/50 p-3 sm:p-4">
          <h3 className="text-white font-semibold mb-2 sm:mb-3 text-sm sm:text-base">📊 Compression Summary</h3>
          <div className="space-y-2">
            <div className="flex justify-between text-xs sm:text-sm flex-col sm:flex-row gap-1">
              <span className="text-slate-400">Archive Name:</span>
              <span className="text-white font-mono break-all text-xs">{compressionResult.archive}</span>
            </div>
          </div>
        </div>

        <div className="mb-6 sm:mb-8 flex flex-col sm:flex-row gap-2 sm:gap-3">
          <a
            href={compressionResult.download_url}
            download={compressionResult.archive}
            className="flex-1 rounded-lg bg-blue-600 px-4 sm:px-6 py-3 text-center font-bold text-white text-sm sm:text-base transition-all hover:bg-blue-700 active:scale-95"
          >
            Download Archive
          </a>
          <button
            onClick={onNewCompression}
            className="flex-1 rounded-lg bg-slate-700 px-4 sm:px-6 py-3 font-bold text-white text-sm sm:text-base transition-all hover:bg-slate-600 active:scale-95"
          >
            Compress More
          </button>
        </div>

        <div className="rounded-lg border border-slate-700 bg-slate-900/50 p-3 sm:p-4">
          <p className="text-xs sm:text-sm text-slate-300">
            <strong>Note:</strong> Your archive can be decompressed anytime to
            recover the original images. Upload it again and select
            &quot;Decompress&quot; mode.
          </p>
        </div>
      </div>
    );
  }

  if (decompressedResult) {
    const hasFiles = decompressedResult.files.length > 0;
    const imageFormatLabel =
      {
        original: 'Original',
        png: 'PNG',
        jpeg: 'JPEG',
        webp: 'WebP',
      }[decompressedResult.image_format] || 'Original';

    return (
      <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-4 sm:p-6 md:p-8 backdrop-blur">
        <div className="mb-6 sm:mb-8 text-center">
          <p className="mb-2 text-xs sm:text-sm font-bold uppercase tracking-wide text-green-400">
            Extracted
          </p>
          <h2 className="mb-2 text-2xl sm:text-3xl font-bold text-white">Decompressed!</h2>
          <p className="text-xs sm:text-base text-slate-300">
            {decompressedResult.count} image(s) extracted - Download format: {imageFormatLabel}
          </p>
        </div>

        <div className="mb-6 sm:mb-8">
          <div className="mb-3 sm:mb-4 flex flex-col gap-2 sm:gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h3 className="text-base sm:text-lg font-bold text-white">Extracted Images</h3>
            {hasFiles && (
              <a
                href={decompressedResult.download_all_url}
                download={`${decompressedResult.output_folder}.zip`}
                className="inline-flex items-center justify-center rounded-lg bg-blue-600 px-3 sm:px-4 py-2 text-xs sm:text-sm font-bold text-white transition-all hover:bg-blue-700 active:scale-95"
              >
                Download All Images
              </a>
            )}
          </div>

          {hasFiles ? (
            <div className="grid max-h-96 sm:max-h-[32rem] grid-cols-2 sm:grid-cols-2 lg:grid-cols-3 gap-2 sm:gap-4 overflow-y-auto rounded-lg border border-slate-700 bg-slate-900/50 p-3 sm:p-4">
              {decompressedResult.files.map((file) => (
                <div
                  key={file.path}
                  className="overflow-hidden rounded-lg border border-slate-700 bg-slate-950/60"
                >
                  <div className="flex aspect-video items-center justify-center bg-slate-950">
                    <img
                      src={file.preview_url}
                      alt={file.name}
                      className="h-full w-full object-contain"
                    />
                  </div>
                  <div className="space-y-2 p-2 sm:p-3">
                    <div>
                      <p className="truncate text-xs sm:text-sm font-semibold text-white">
                        {file.name}
                      </p>
                      <p className="truncate text-xs text-slate-400">
                        {file.path} - {file.size_mb} MB
                      </p>
                    </div>
                    <a
                      href={file.url}
                      download={file.name}
                      className="block rounded-md bg-slate-700 px-3 py-2 text-center text-xs sm:text-sm font-bold text-white transition-all hover:bg-slate-600 active:scale-95"
                    >
                      Download
                    </a>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-slate-700 bg-slate-900/50 p-3 sm:p-4 text-xs sm:text-sm text-slate-300">
              No images were found in this archive.
            </div>
          )}
        </div>

        <div className="mb-6 sm:mb-8 flex flex-col sm:flex-row gap-2 sm:gap-4">
          <button
            onClick={onNewCompression}
            className="flex-1 rounded-lg bg-blue-600 px-4 sm:px-6 py-3 font-bold text-white text-sm sm:text-base transition-all hover:bg-blue-700 active:scale-95"
          >
            Process Another
          </button>
          <button
            onClick={() => window.location.reload()}
            className="flex-1 rounded-lg bg-slate-700 px-4 sm:px-6 py-3 font-bold text-white text-sm sm:text-base transition-all hover:bg-slate-600 active:scale-95"
          >
            Reset
          </button>
        </div>

        <div className="rounded-lg border border-slate-700 bg-slate-900/50 p-3 sm:p-4">
          <p className="text-xs sm:text-sm text-slate-300">
            <strong>Info:</strong> Use Download All Images to save the extracted
            folder, or download each image separately.
          </p>
        </div>
      </div>
    );
  }

  return null;
}
