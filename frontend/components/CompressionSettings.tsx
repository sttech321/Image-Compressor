'use client';

import type { ImageDownloadFormat } from '@/services/compressorService';

interface CompressionSettingsProps {
  mode: 'compress' | 'decompress';
  isCompressing: boolean;
  onModeChange: (mode: 'compress' | 'decompress') => void;
  onCompress: () => void;
  onDecompress: () => void;
  filesSelected: boolean;
  quality: number;
  onQualityChange: (quality: number) => void;
  outputFormat: 'dcv' | 'zip';
  onFormatChange: (format: 'dcv' | 'zip') => void;
  lossless: boolean;
  onLosslessChange: (lossless: boolean) => void;
  imageDownloadFormat: ImageDownloadFormat;
  onImageDownloadFormatChange: (format: ImageDownloadFormat) => void;
}

const imageFormatOptions: { label: string; value: ImageDownloadFormat }[] = [
  { label: 'Original', value: 'original' },
  { label: 'PNG', value: 'png' },
  { label: 'JPEG', value: 'jpeg' },
  { label: 'WebP', value: 'webp' },
];

const getQualityLabel = (quality: number) => {
  if (quality <= 18) return 'Best quality';
  if (quality <= 32) return 'Balanced';
  if (quality <= 42) return 'Smaller file';
  return 'Smallest file';
};

const qualityPresets = [
  { label: 'Best', value: 18 },
  { label: 'Balanced', value: 28 },
  { label: 'Smallest', value: 42 },
];

export default function CompressionSettings({
  mode,
  isCompressing,
  onModeChange,
  onCompress,
  onDecompress,
  filesSelected,
  quality,
  onQualityChange,
  outputFormat,
  onFormatChange,
  lossless,
  onLosslessChange,
  imageDownloadFormat,
  onImageDownloadFormatChange,
}: CompressionSettingsProps) {
  return (
    <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg xs:rounded-xl p-3 xs:p-4 sm:p-5 md:p-6 lg:p-8 lg:sticky lg:top-8">
      <h2 className="text-lg xs:text-xl sm:text-2xl font-bold text-white mb-3 xs:mb-4 sm:mb-6">⚙️ Settings</h2>

      {/* Mode Selection */}
      <div className="mb-4 sm:mb-6">
        <label className="text-slate-300 text-xs sm:text-sm font-semibold mb-2 sm:mb-3 block">
          Mode
        </label>
        <div className="grid grid-cols-2 gap-2 sm:gap-3">
          <button
            onClick={() => onModeChange('compress')}
            className={`py-2.5 sm:py-3 px-3 sm:px-4 rounded-lg font-semibold text-sm sm:text-base transition-all active:scale-95 ${
              mode === 'compress'
                ? 'bg-blue-600 text-white'
                : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
          >
            📦 Compress
          </button>
          <button
            onClick={() => onModeChange('decompress')}
            className={`py-2 xs:py-2.5 sm:py-3 px-2 xs:px-3 sm:px-4 rounded-lg font-semibold text-xs xs:text-sm sm:text-base transition-all active:scale-95 ${
              mode === 'decompress'
                ? 'bg-blue-600 text-white'
                : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
          >
            📂 Decompress
          </button>
        </div>
      </div>

      {/* Compression Controls - Only show in compress mode */}
      {mode === 'compress' && (
        <>
          {/* Quality Slider */}
          <div className="mb-3 xs:mb-4 sm:mb-6">
            <div className="mb-2 flex items-center justify-between gap-3">
              <label className="text-slate-300 text-xs xs:text-sm font-semibold">
                Image Quality
              </label>
              <span className="rounded-md bg-blue-600/15 px-2 py-1 text-xs font-bold text-blue-300">
                {getQualityLabel(quality)}
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="50"
              value={quality}
              onChange={(e) => onQualityChange(parseInt(e.target.value))}
              className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-600"
            />
            <div className="mt-1.5 flex justify-between text-[11px] font-semibold text-slate-400 xs:mt-2">
              <span>Best quality</span>
              <span>Smaller file</span>
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2">
              {qualityPresets.map((preset) => (
                <button
                  key={preset.value}
                  onClick={() => onQualityChange(preset.value)}
                  className={`rounded-md px-2 py-2 text-xs font-semibold transition-all active:scale-95 ${
                    quality === preset.value
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  }`}
                >
                  {preset.label}
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-slate-400">
              Recommended: Balanced for most images.
            </p>
          </div>

          {/* Output Format Selection */}
          <div className="mb-3 xs:mb-4 sm:mb-6">
            <label className="text-slate-300 text-xs xs:text-sm font-semibold mb-2 block">
              Archive Format
            </label>
            <div className="grid grid-cols-2 gap-2 xs:gap-2.5 sm:gap-3">
              <button
                onClick={() => onFormatChange('dcv')}
                className={`py-2 xs:py-2.5 sm:py-3 px-2 xs:px-3 sm:px-4 rounded-lg font-semibold transition-all text-xs xs:text-sm active:scale-95 ${
                  outputFormat === 'dcv'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                📦 .DCV Archive
              </button>
              <button
                onClick={() => onFormatChange('zip')}
                className={`py-2 xs:py-2.5 sm:py-3 px-2 xs:px-3 sm:px-4 rounded-lg font-semibold transition-all text-xs xs:text-sm active:scale-95 ${
                  outputFormat === 'zip'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                📁 ZIP Files
              </button>
            </div>
          </div>

          {/* Lossless Toggle */}
          <div className="mb-3 xs:mb-4 sm:mb-6">
            <label className="text-slate-300 text-xs xs:text-sm font-semibold mb-2 flex items-center gap-2 xs:gap-3">
              <input
                type="checkbox"
                checked={lossless}
                onChange={(e) => onLosslessChange(e.target.checked)}
                className="w-3.5 xs:w-4 h-3.5 xs:h-4 rounded cursor-pointer accent-blue-600"
              />
              Lossless Mode
            </label>
            <p className="text-xs text-slate-400 ml-6 xs:ml-7">
              {lossless ? '🔒 Preserves original quality' : '📉 Allows quality reduction'}
            </p>
          </div>
        </>
      )}

      {mode === 'decompress' && (
        <div className="mb-3 xs:mb-4 sm:mb-6">
          <label className="text-slate-300 text-xs xs:text-sm font-semibold mb-2 block">
            Download Image Format
          </label>
          <div className="grid grid-cols-2 gap-2 xs:gap-2.5 sm:gap-3">
            {imageFormatOptions.map((option) => (
              <button
                key={option.value}
                onClick={() => onImageDownloadFormatChange(option.value)}
                className={`py-2 xs:py-2.5 sm:py-3 px-2 xs:px-3 sm:px-4 rounded-lg font-semibold transition-all text-xs xs:text-sm active:scale-95 ${
                  imageDownloadFormat === option.value
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Info Box */}
      <div className="mb-3 xs:mb-4 sm:mb-6 bg-slate-900/50 border border-slate-700 rounded-lg p-2.5 xs:p-3 sm:p-4">
        <h3 className="text-xs xs:text-sm font-bold text-yellow-300 mb-1.5 xs:mb-2">
          ✨ What Improves
        </h3>
        <ul className="text-xs text-slate-300 space-y-0.5 xs:space-y-1">
          <li>✓ Less visual clutter</li>
          <li>✓ Faster decisions</li>
          <li>✓ Quality guidance</li>
          <li>✓ Target dimensions control</li>
        </ul>
      </div>

      {/* Action Button */}
      <button
        onClick={mode === 'compress' ? onCompress : onDecompress}
        disabled={!filesSelected || isCompressing}
        className={`w-full py-2.5 xs:py-3 sm:py-3 px-3 xs:px-4 sm:px-6 rounded-lg font-bold text-white text-xs xs:text-sm sm:text-base transition-all active:scale-95 ${
          isCompressing
            ? 'bg-slate-600 cursor-not-allowed'
            : filesSelected
              ? 'bg-blue-600 hover:bg-blue-700'
              : 'bg-slate-600 cursor-not-allowed opacity-50'
        }`}
      >
        {isCompressing ? (
          <span className="flex items-center justify-center gap-2">
            <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
            <span>{mode === 'compress' ? 'Compressing...' : 'Decompressing...'}</span>
          </span>
        ) : mode === 'compress' ? (
          'Compress Images'
        ) : (
          'Decompress Archive'
        )}
      </button>
    </div>
  );
}
