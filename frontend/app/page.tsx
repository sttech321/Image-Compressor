'use client';

import { useState } from 'react';
import ImageUpload from '@/components/ImageUpload';
import CompressionSettings from '@/components/CompressionSettings';
import ResultsDisplay from '@/components/ResultsDisplay';
import {
  compressImages,
  decompressArchive,
  type CompressionResponse,
  type DecompressionResponse,
  type ImageDownloadFormat,
} from '@/services/compressorService';

const toolDescriptions = {
  compress: {
    eyebrow: 'Client-ready image delivery',
    title: 'Make large image sets easier to send, store, and publish.',
    body: 'Compress images in bulk so project folders stay lightweight while the visuals remain useful for reviews, websites, and handoffs.',
    impactLabel: 'Best for',
    impactValue: 'Client handoffs, website assets, and organized project archives.',
    outputLabel: 'Output',
    outputValue: '.DCV or ZIP',
    points: [
      {
        title: 'Faster sharing',
        body: 'Reduce image weight so uploads, downloads, and file transfers feel smoother.',
      },
      {
        title: 'Website friendly',
        body: 'Keep pages lighter without manually resizing every image one by one.',
      },
      {
        title: 'Folder workflow',
        body: 'Upload a complete folder and package the result into one clean archive.',
      },
    ],
  },
  decompress: {
    eyebrow: 'Archive recovery',
    title: 'Open a .dcv archive and deliver images in the right format.',
    body: 'Use decompression when a client or team member needs the original files back from a saved archive.',
    impactLabel: 'Best for',
    impactValue: 'Recovering archived image sets and preparing files for delivery.',
    outputLabel: 'Exports',
    outputValue: 'Original, PNG, JPEG, or WebP',
    points: [
      {
        title: 'Recover files',
        body: 'Extract all images from the archive and preview them before downloading.',
      },
      {
        title: 'Flexible delivery',
        body: 'Download files individually, together, or in the image format the client needs.',
      },
      {
        title: 'Clean handoff',
        body: 'Turn one compressed archive back into a ready-to-share image folder.',
      },
    ],
  },
};

export default function Home() {
  const [files, setFiles] = useState<File[]>([]);
  const [isCompressing, setIsCompressing] = useState(false);
  const [compressionResult, setCompressionResult] =
    useState<CompressionResponse | null>(null);
  const [decompressedResult, setDecompressedResult] =
    useState<DecompressionResponse | null>(null);
  const [error, setError] = useState<string>('');
  const [mode, setMode] = useState<'compress' | 'decompress'>('compress');
  const [quality, setQuality] = useState(28);
  const [outputFormat, setOutputFormat] = useState<'dcv' | 'zip'>('dcv');
  const [lossless, setLossless] = useState(false);
  const [imageDownloadFormat, setImageDownloadFormat] =
    useState<ImageDownloadFormat>('original');
  const [originalSize, setOriginalSize] = useState(0);
  const toolDescription = toolDescriptions[mode];

  const handleFilesSelected = (selectedFiles: File[]) => {
    setFiles(selectedFiles);
    setError('');
    setCompressionResult(null);
    // Calculate total file size
    const totalSize = selectedFiles.reduce((sum, file) => sum + file.size, 0);
    setOriginalSize(totalSize);
  };

  const handleCompress = async () => {
    if (files.length === 0) {
      setError('Please select at least one image');
      return;
    }

    setIsCompressing(true);
    setError('');

    try {
      const result = await compressImages(files, quality.toString(), lossless, outputFormat);
      setCompressionResult({ ...result, original_size_mb: originalSize / (1024 * 1024) });
      setFiles([]);
      setOriginalSize(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Compression failed');
    } finally {
      setIsCompressing(false);
    }
  };

  const handleDecompress = async () => {
    if (files.length === 0) {
      setError('Please select a .dcv archive file');
      return;
    }

    if (!files[0].name.endsWith('.dcv')) {
      setError('File must be a .dcv archive');
      return;
    }

    setIsCompressing(true);
    setError('');

    try {
      const result = await decompressArchive(files[0], imageDownloadFormat);
      setDecompressedResult(result);
      setFiles([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Decompression failed');
    } finally {
      setIsCompressing(false);
    }
  };

  const resetForm = () => {
    setFiles([]);
    setCompressionResult(null);
    setDecompressedResult(null);
    setError('');
    setOriginalSize(0);
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="container mx-auto px-2 xs:px-3 sm:px-4 md:px-6 py-4 xs:py-6 sm:py-8 md:py-12 lg:py-16">
        {/* Header */}
        <div className="text-center mb-6 xs:mb-8 sm:mb-10 md:mb-12 lg:mb-16">
          <h1 className="text-2xl xs:text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold text-white mb-2 xs:mb-3 sm:mb-4">
            📷 Image Compressor
          </h1>
          <p className="text-xs xs:text-sm sm:text-base md:text-lg lg:text-xl text-slate-300 px-2">
            Professional AV1 intra-frame compression — ~40% smaller than JPEG at
            an equivalent quality, held to a perceptually lossless ~38&nbsp;dB PSNR.
          </p>
        </div>

        {/* Main Content */}
        {!compressionResult && !decompressedResult ? (
          <div className="grid grid-cols-1 md:grid-cols-1 lg:grid-cols-3 gap-3 xs:gap-4 sm:gap-5 md:gap-6 lg:gap-8">
            {/* Left - Upload Area */}
            <div className="order-2 md:order-1 lg:col-span-2">
              <ImageUpload
                onFilesSelected={handleFilesSelected}
                selectedFiles={files}
                onClear={() => setFiles([])}
                mode={mode}
              />
              <section className="mt-4 xs:mt-5 sm:mt-6 overflow-hidden rounded-lg xs:rounded-xl border border-slate-700 bg-slate-800/40 backdrop-blur">
                <div className="grid gap-0 lg:grid-cols-[1.55fr_0.9fr]">
                  <div className="p-4 xs:p-5 sm:p-6 md:p-8">
                    <p className="mb-2 text-xs font-bold uppercase text-blue-300">
                      {toolDescription.eyebrow}
                    </p>
                    <h2 className="max-w-3xl text-lg font-bold text-white xs:text-xl sm:text-2xl">
                      {toolDescription.title}
                    </h2>
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300 sm:text-base">
                      {toolDescription.body}
                    </p>

                    <ol className="mt-5 grid gap-4 sm:grid-cols-3">
                      {toolDescription.points.map((point, index) => (
                        <li key={point.title} className="flex gap-3">
                          <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full border border-blue-400/40 bg-blue-500/10 text-xs font-bold text-blue-200">
                            {String(index + 1).padStart(2, '0')}
                          </span>
                          <div>
                            <h3 className="text-sm font-bold text-white">
                              {point.title}
                            </h3>
                            <p className="mt-1 text-xs leading-5 text-slate-400">
                              {point.body}
                            </p>
                          </div>
                        </li>
                      ))}
                    </ol>
                  </div>

                  <aside className="border-t border-slate-700 bg-slate-950/20 p-4 xs:p-5 sm:p-6 md:p-8 lg:border-l lg:border-t-0">
                    <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-lg border border-blue-400/30 bg-blue-500/10 text-xl font-black text-blue-200">
                      {mode === 'compress' ? 'C' : 'D'}
                    </div>
                    <p className="text-sm font-bold text-white">Client impact</p>
                    <p className="mt-2 text-sm leading-6 text-slate-300">
                      Clear purpose, smaller handoffs, and fewer questions about
                      how files should be delivered.
                    </p>
                    <dl className="mt-6 space-y-4 border-t border-slate-700 pt-5">
                      <div>
                        <dt className="text-xs font-semibold uppercase text-slate-500">
                          {toolDescription.impactLabel}
                        </dt>
                        <dd className="mt-1 text-sm font-semibold text-slate-100">
                          {toolDescription.impactValue}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs font-semibold uppercase text-slate-500">
                          {toolDescription.outputLabel}
                        </dt>
                        <dd className="mt-1 text-sm font-semibold text-slate-100">
                          {toolDescription.outputValue}
                        </dd>
                      </div>
                    </dl>
                  </aside>
                </div>
              </section>
            </div>

            {/* Right - Settings */}
            <div className="order-1 md:order-2">
              <CompressionSettings
                mode={mode}
                isCompressing={isCompressing}
                onModeChange={setMode}
                onCompress={handleCompress}
                onDecompress={handleDecompress}
                filesSelected={files.length > 0}
                quality={quality}
                onQualityChange={setQuality}
                outputFormat={outputFormat}
                onFormatChange={setOutputFormat}
                lossless={lossless}
                onLosslessChange={setLossless}
                imageDownloadFormat={imageDownloadFormat}
                onImageDownloadFormatChange={setImageDownloadFormat}
              />
            </div>
          </div>
        ) : (
          <ResultsDisplay
            compressionResult={compressionResult}
            decompressedResult={decompressedResult}
            onNewCompression={resetForm}
            originalSize={originalSize}
          />
        )}

        {/* Error Message */}
        {error && (
          <div className="mt-4 xs:mt-6 sm:mt-8 p-3 xs:p-4 sm:p-5 bg-red-900/20 border border-red-500 rounded-lg text-red-300 text-xs xs:text-sm sm:text-base">
            {error}
          </div>
        )}
      </div>
    </main>
  );
}
