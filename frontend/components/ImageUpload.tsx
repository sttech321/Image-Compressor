'use client';

import { useState, useRef } from 'react';

interface ImageUploadProps {
  onFilesSelected: (files: File[]) => void;
  selectedFiles: File[];
  onClear: () => void;
  mode: 'compress' | 'decompress';
}

export default function ImageUpload({
  onFilesSelected,
  selectedFiles,
  onClear,
  mode,
}: ImageUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const isCompressMode = mode === 'compress';

  const folderInputProps = {
    webkitdirectory: '',
    directory: '',
  } as React.InputHTMLAttributes<HTMLInputElement> & {
    webkitdirectory: string;
    directory: string;
  };

  const acceptedTypes = [
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/bmp',
    'image/tiff',
    'application/octet-stream',
  ];

  const acceptedExtensions = [
    '.jpg',
    '.jpeg',
    '.png',
    '.webp',
    '.bmp',
    '.tif',
    '.tiff',
    '.dcv',
  ];

  const fileAccept = isCompressMode
    ? 'image/jpeg,image/png,image/webp,image/bmp,image/tiff'
    : '.dcv';

  const getDisplayName = (file: File) => file.webkitRelativePath || file.name;

  const isAcceptedFile = (file: File) => {
    const fileName = file.name.toLowerCase();

    if (!isCompressMode) {
      return fileName.endsWith('.dcv');
    }

    return (
      acceptedTypes.includes(file.type) ||
      acceptedExtensions
        .filter((extension) => extension !== '.dcv')
        .some((extension) => fileName.endsWith(extension))
    );
  };

  const addFiles = (files: File[]) => {
    const acceptedFiles = files.filter(isAcceptedFile);

    if (acceptedFiles.length > 0) {
      onFilesSelected([...selectedFiles, ...acceptedFiles]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    addFiles(Array.from(e.dataTransfer.files));
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    addFiles(files);
    e.target.value = '';
  };

  const handleFolderInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    addFiles(files);
    e.target.value = '';
  };

  const removeFile = (index: number) => {
    onFilesSelected(selectedFiles.filter((_, i) => i !== index));
  };

  return (
    <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg xs:rounded-xl p-3 xs:p-4 sm:p-5 md:p-6 lg:p-8">
      {/* Drag and Drop Area */}
      {selectedFiles.length === 0 ? (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-lg p-4 xs:p-6 sm:p-8 md:p-10 lg:p-12 text-center transition-all ${
            isDragging
              ? 'border-blue-400 bg-blue-400/10'
              : 'border-slate-600 bg-slate-900/30 hover:border-slate-500'
          }`}
        >
          <div className="text-2xl xs:text-3xl sm:text-4xl mb-2 xs:mb-3 sm:mb-4">📁</div>
          <h2 className="text-base xs:text-lg sm:text-xl md:text-2xl font-bold text-white mb-1 xs:mb-2">
            {isCompressMode
              ? 'Drop images or choose a folder.'
              : 'Drop a .dcv archive.'}
          </h2>
          <p className="text-xs xs:text-sm sm:text-base text-slate-400 mb-3 xs:mb-4 sm:mb-6">
            {isCompressMode
              ? 'Upload single images or a full folder of images.'
              : 'Upload a compressed .dcv file to extract images.'}
          </p>
          <div className="flex flex-col items-center justify-center gap-2 sm:flex-row sm:gap-3">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="inline-block px-5 xs:px-6 sm:px-8 py-2 xs:py-2.5 sm:py-3 cursor-pointer bg-slate-700 hover:bg-slate-600 active:scale-95 text-white text-xs xs:text-sm sm:text-base rounded-full font-semibold transition-all"
            >
              {isCompressMode ? 'Choose images' : 'Choose archive'}
            </button>
            {isCompressMode && (
              <button
                onClick={() => folderInputRef.current?.click()}
                className="inline-block px-5 xs:px-6 sm:px-8 py-2 xs:py-2.5 sm:py-3 cursor-pointer bg-blue-600 hover:bg-blue-700 active:scale-95 text-white text-xs xs:text-sm sm:text-base rounded-full font-semibold transition-all"
              >
                Choose folder
              </button>
            )}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={fileAccept}
            onChange={handleFileInputChange}
            className="hidden"
          />
          <input
            ref={folderInputRef}
            type="file"
            multiple
            accept={fileAccept}
            onChange={handleFolderInputChange}
            className="hidden"
            {...folderInputProps}
          />
        </div>
      ) : (
        <div>
          <h3 className="text-white font-bold text-sm xs:text-base sm:text-lg mb-2 xs:mb-3 sm:mb-4">
            Selected Files ({selectedFiles.length})
          </h3>
          <div className="space-y-2 max-h-72 xs:max-h-80 sm:max-h-96 md:max-h-[28rem] lg:max-h-[32rem] overflow-y-auto mb-3 xs:mb-4">
            {selectedFiles.map((file, index) => (
              <div
                key={index}
                className="flex items-center justify-between bg-slate-700/50 p-3 rounded-lg gap-2"
              >
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <span className="text-base xs:text-lg sm:text-xl flex-shrink-0">
                    {file.name.endsWith('.dcv') ? '📦' : '🖼️'}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-white text-xs xs:text-sm font-medium truncate">
                      {getDisplayName(file)}
                    </p>
                    <p className="text-slate-400 text-xs">
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => removeFile(index)}
                  className="text-red-400 hover:text-red-300 active:scale-110 px-2 py-1 flex-shrink-0 transition-transform"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-2 xs:gap-2.5 sm:gap-3">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="px-3 xs:px-4 py-2 xs:py-2.5 sm:py-3 bg-slate-700 hover:bg-slate-600 active:scale-95 text-white rounded-lg text-xs xs:text-sm font-semibold transition-all"
            >
              {isCompressMode ? '+ Add Images' : '+ Change Archive'}
            </button>
            {isCompressMode && (
              <button
                onClick={() => folderInputRef.current?.click()}
                className="px-3 xs:px-4 py-2 xs:py-2.5 sm:py-3 bg-slate-700 hover:bg-slate-600 active:scale-95 text-white rounded-lg text-xs xs:text-sm font-semibold transition-all"
              >
                + Add Folder
              </button>
            )}
            <button
              onClick={onClear}
              className={`${isCompressMode ? 'col-span-2' : ''} px-3 xs:px-4 py-2 xs:py-2.5 sm:py-3 bg-slate-600 hover:bg-slate-500 active:scale-95 text-white rounded-lg text-xs xs:text-sm font-semibold transition-all`}
            >
              Clear All
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={fileAccept}
            onChange={handleFileInputChange}
            className="hidden"
          />
          <input
            ref={folderInputRef}
            type="file"
            multiple
            accept={fileAccept}
            onChange={handleFolderInputChange}
            className="hidden"
            {...folderInputProps}
          />
        </div>
      )}
    </div>
  );
}
