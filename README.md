# Image Compressor App

A full-stack web application for compressing images using AV1 video codec. Features a clean React/Next.js frontend and Python Flask backend.

## Features

✨ **Compress Images**: Reduce image file sizes by 60-90% using AV1 encoding  
📦 **Create Archives**: Multiple images are grouped into .dcv archives  
🔄 **Decompress**: Recover original images from .dcv archives  
🎚️ **Quality Control**: Adjust compression quality and lossless options  
🖥️ **User-Friendly**: Modern dark-themed web interface  
✅ **Free & Secure**: All processing done locally on your server

## System Requirements

- Python 3.9+
- Node.js 18+ and npm
- ffmpeg with AV1 support (libaom-av1)
- Windows, macOS, or Linux

## Project Structure

```
image-compressor-app/
├── backend/
│   ├── app.py              # Flask server
│   ├── requirements.txt    # Python dependencies
│   ├── .env               # Backend configuration
│   ├── uploads/           # Temporary file storage
│   └── dcv-picture-compressor/  # Python compressor
├── frontend/
│   ├── app/              # Next.js app router
│   ├── components/       # React components
│   ├── services/         # API client services
│   ├── package.json
│   ├── .env.local
│   └── tailwind.config.ts
└── README.md
```

## Installation & Setup

### 1. Install Backend Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 3. Verify ffmpeg

Make sure ffmpeg with AV1 support is installed:

```bash
ffmpeg -encoders | grep av1
```

If not found, install ffmpeg:
- **Windows**: Download from [BtbN FFmpeg Builds](https://github.com/BtbN/FFmpeg-Builds/releases)
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg`

## Running the Application

### Start Backend (Terminal 1)

```bash
cd backend
python app.py
```

Backend will run on `http://localhost:5000`

### Start Frontend (Terminal 2)

```bash
cd frontend
npm run dev
```

Frontend will run on `http://localhost:3000`

### Access the App

Open your browser and go to: **http://localhost:3000**

## Usage

### Compress Images

1. **Upload Images**: Drag and drop images or click "Choose image"
2. **Adjust Settings**:
   - Set compression quality (0-63, lower = smaller file)
   - Enable lossless for bit-perfect quality (larger files)
3. **Compress**: Click "Compress Images"
4. **Download**: Get the .dcv archive

### Decompress Archive

1. **Select Archive**: Upload a .dcv file
2. **Switch Mode**: Click "Decompress" mode
3. **Extract**: Click "Decompress Archive"
4. **View Files**: See all extracted images

## Configuration

### Backend (.env)

```env
FLASK_ENV=development
FLASK_DEBUG=True
UPLOAD_FOLDER=uploads
OUTPUT_FOLDER=uploads/output
MAX_FILE_SIZE=524288000  # 500MB
```

### Frontend (.env.local)

```env
NEXT_PUBLIC_API_URL=http://localhost:5000
```

## API Endpoints

### POST /api/compress
Compress images

**Request**:
- `files`: Multiple image files
- `quality`: CRF value (0-63)
- `lossless`: Boolean (true/false)

**Response**:
```json
{
  "status": "success",
  "archive": "compressed_job_1.dcv",
  "size_mb": 25.5,
  "download_url": "/api/download/compressed_job_1.dcv"
}
```

### POST /api/decompress
Decompress archive

**Request**:
- `file`: .dcv archive file

**Response**:
```json
{
  "status": "success",
  "files": ["photo1.png", "photo2.png"],
  "count": 2,
  "output_folder": "decompressed_archive"
}
```

### GET /api/download/<filename>
Download file

### GET /api/health
Health check

## Performance Tips

- **Quality**: Default CRF 28 provides good balance. Lower values = better quality but larger files
- **Lossless**: Use only when you need perfect quality (10-15% compression vs 90% with lossy)
- **Batch**: Compress similar photos together for better compression
- **Format**: JPEG photos compress best (often 90%+)

## Troubleshooting

### ffmpeg not found
```bash
# Windows
$env:Path += ";C:\ffmpeg\bin"

# macOS/Linux
export PATH="/usr/local/bin:$PATH"
```

### CORS errors
Ensure frontend and backend URLs match in `.env.local`

### Large files timeout
Increase timeout in `app.py` (currently 600 seconds)

### Permission denied (uploads)
Ensure `uploads/` directory is writable

## Development

### Install additional dev dependencies

```bash
cd frontend
npm install

cd ../backend
pip install flask-cors python-dotenv
```

### Build for production

```bash
cd frontend
npm run build
npm run start
```

## License

Based on [dcv-picture-compressor](https://github.com/fixzip/dcv-picture-compressor)

## Credits

- Image compression engine: [dcv-picture-compressor](https://github.com/fixzip/dcv-picture-compressor)
- Frontend: Next.js + React + Tailwind CSS
- Backend: Flask + Python
