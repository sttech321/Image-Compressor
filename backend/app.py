import os
import sys
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from pathlib import Path, PurePosixPath
import subprocess
import shutil
import io
import zipfile
import tempfile
from urllib.parse import quote
from PIL import Image

# Add compressor directory to path for archive metadata helpers.
COMPRESSOR_FOLDER = os.path.join(os.path.dirname(__file__), 'dcv-picture-compressor')
if COMPRESSOR_FOLDER not in sys.path:
    sys.path.insert(0, COMPRESSOR_FOLDER)

app = Flask(__name__)
CORS(app)

# Configuration
# UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
UPLOAD_FOLDER = tempfile.gettempdir()
OUTPUT_FOLDER = os.path.join(UPLOAD_FOLDER, 'output')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp', 'tif', 'tiff', 'dcv'}
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp', 'tif', 'tiff'}
IMAGE_DOWNLOAD_FORMATS = {'original', 'png', 'jpeg', 'webp'}
IMAGE_DOWNLOAD_EXTENSIONS = {'png': 'png', 'jpeg': 'jpg', 'webp': 'webp'}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE


def _default_ffmpeg_path():
    explicit = os.environ.get('FFMPEG_PATH')
    if explicit:
        return explicit
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg:
        return str(Path(ffmpeg).parent)
    if os.name == 'nt':
        return r'C:\ffmpeg\bin'
    return '/usr/bin'


FFMPEG_PATH = _default_ffmpeg_path()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_upload_file_path(root_folder, filename):
    """Resolve an uploaded file path while preserving safe folder names."""
    root_path = Path(root_folder).resolve()
    relative_path = PurePosixPath(filename.replace('\\', '/'))

    if relative_path.is_absolute() or any(
        part in ('', '.', '..') for part in relative_path.parts
    ):
        raise ValueError('Invalid upload path')

    safe_parts = [secure_filename(part) for part in relative_path.parts]
    if not safe_parts or any(not part for part in safe_parts):
        raise ValueError('Invalid upload path')

    file_path = root_path.joinpath(*safe_parts).resolve()
    if file_path != root_path and root_path not in file_path.parents:
        raise ValueError('Invalid upload path')

    return file_path

def get_compressor_script():
    """Get the path to the compressor script"""
    compressor_path = os.path.join(COMPRESSOR_FOLDER, 'stockphoto_video.py')
    if not os.path.exists(compressor_path):
        raise FileNotFoundError(f"Compressor script not found at {compressor_path}")
    return compressor_path

def get_archive_original_sizes(archive_path):
    """Read original file-size metadata from newer .dcv archives."""
    try:
        from stockphoto_video import read_archive_original_sizes
        return read_archive_original_sizes(archive_path)
    except Exception:
        return {}

def get_output_folder(folder):
    """Resolve a decompressed output folder safely inside OUTPUT_FOLDER."""
    output_root = Path(OUTPUT_FOLDER).resolve()
    folder_path = (output_root / secure_filename(folder)).resolve()

    if folder_path != output_root and output_root not in folder_path.parents:
        raise ValueError('Invalid folder path')

    return folder_path

def get_output_file(folder, filename):
    """Resolve a nested decompressed file safely inside its output folder."""
    folder_path = get_output_folder(folder)
    relative_parts = PurePosixPath(filename.replace('\\', '/')).parts

    if any(part in ('', '.', '..') for part in relative_parts):
        raise ValueError('Invalid file path')

    file_path = folder_path.joinpath(*relative_parts).resolve()

    if file_path != folder_path and folder_path not in file_path.parents:
        raise ValueError('Invalid file path')

    return file_path

def build_file_url(route, folder, relative_path):
    """Build an API URL for a nested decompressed file."""
    safe_folder = secure_filename(folder)
    safe_path = quote(relative_path.as_posix(), safe='/')
    return f'/api/{route}/{safe_folder}/{safe_path}'

def normalize_image_format(value):
    """Validate requested decompressed image format."""
    image_format = (value or 'original').lower()
    if image_format == 'jpg':
        image_format = 'jpeg'

    if image_format not in IMAGE_DOWNLOAD_FORMATS:
        raise ValueError('Invalid image format')

    return image_format

def image_has_alpha(image):
    """Return whether a Pillow image carries transparent pixels."""
    return image.mode in ('RGBA', 'LA') or (
        image.mode == 'P' and 'transparency' in image.info
    )

def unique_output_path(target_path):
    """Avoid overwriting when multiple source formats share the same stem."""
    if not target_path.exists():
        return target_path

    parent = target_path.parent
    stem = target_path.stem
    suffix = target_path.suffix
    counter = 1

    while True:
        candidate = parent / f'{stem}_{counter}{suffix}'
        if not candidate.exists():
            return candidate
        counter += 1

def save_image_as(source_path, target_path, image_format):
    """Convert one decompressed image to a browser-friendly download format."""
    with Image.open(source_path) as image:
        if image_format == 'jpeg':
            if image_has_alpha(image):
                rgba = image.convert('RGBA')
                background = Image.new('RGB', rgba.size, (255, 255, 255))
                background.paste(rgba, mask=rgba.getchannel('A'))
                image = background
            else:
                image = image.convert('RGB')
            image.save(target_path, 'JPEG', quality=95, optimize=True)
            return

        if image_format == 'webp':
            image = image.convert('RGBA' if image_has_alpha(image) else 'RGB')
            image.save(target_path, 'WEBP', quality=95, method=6)
            return

        if image.mode not in ('1', 'L', 'LA', 'P', 'RGB', 'RGBA', 'I;16'):
            image = image.convert('RGBA' if image_has_alpha(image) else 'RGB')
        image.save(target_path, 'PNG', optimize=True)

def convert_decompressed_images(folder_path, image_format):
    """Convert extracted image files in place when a target format is selected."""
    if image_format == 'original':
        return

    target_extension = IMAGE_DOWNLOAD_EXTENSIONS[image_format]

    for file_path in sorted(folder_path.rglob('*')):
        if not file_path.is_file():
            continue

        source_extension = file_path.suffix.lower().lstrip('.')
        if source_extension not in IMAGE_EXTENSIONS:
            continue

        if source_extension == target_extension:
            continue

        if image_format == 'jpeg' and source_extension in {'jpg', 'jpeg'}:
            continue

        target_path = unique_output_path(file_path.with_suffix(f'.{target_extension}'))
        save_image_as(file_path, target_path, image_format)
        file_path.unlink(missing_ok=True)

def list_decompressed_files(folder_path, folder_name, original_sizes=None):
    """Return all decompressed image files recursively."""
    original_sizes = original_sizes or {}
    files = []

    for file_path in sorted(folder_path.rglob('*')):
        if not file_path.is_file():
            continue

        if file_path.suffix.lower().lstrip('.') not in IMAGE_EXTENSIONS:
            continue

        relative_path = file_path.relative_to(folder_path)
        actual_size = file_path.stat().st_size
        original_size = original_sizes.get(relative_path.as_posix())
        display_size = original_size or actual_size
        files.append({
            'name': file_path.name,
            'path': relative_path.as_posix(),
            'size': display_size,
            'size_mb': round(display_size / (1024 * 1024), 2),
            'actual_size': actual_size,
            'actual_size_mb': round(actual_size / (1024 * 1024), 2),
            'original_size': original_size,
            'original_size_mb': (
                round(original_size / (1024 * 1024), 2)
                if original_size is not None
                else None
            ),
            'url': build_file_url('download-file', folder_name, relative_path),
            'preview_url': build_file_url('preview-file', folder_name, relative_path),
        })

    return files

@app.route('/', methods=['GET'])
def index():
    """Landing page for direct visits to the API host (e.g. localhost:5000)."""
    return jsonify({
        'service': 'Image Compressor API',
        'status': 'ok',
        'message': 'API is running. Open the web UI at http://localhost:3000 (not this URL).',
        'health': '/api/health',
        'endpoints': {
            'compress': 'POST /api/compress',
            'decompress': 'POST /api/decompress',
            'download': 'GET /api/download/<filename>',
        },
    }), 200


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'message': 'Server is running'}), 200

@app.route('/api/compress', methods=['POST'])
def compress():
    """Compress images in a folder or archive them"""
    try:
        if 'files' not in request.files and 'folder' not in request.form:
            return jsonify({'error': 'No files or folder provided'}), 400

        quality = request.form.get('quality', '28')
        lossless = request.form.get('lossless', 'false').lower() == 'true'
        output_format = request.form.get('format', 'dcv')  # 'dcv' or 'zip'

        # Create a temporary folder for this compression job
        job_id = Path(UPLOAD_FOLDER).glob('*').__sizeof__()
        job_folder = os.path.join(UPLOAD_FOLDER, f'job_{int(job_id)}')
        os.makedirs(job_folder, exist_ok=True)

        # Save uploaded files
        if 'files' in request.files:
            files = request.files.getlist('files')
            for file in files:
                if file and allowed_file(file.filename):
                    file_path = get_upload_file_path(job_folder, file.filename)
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file.save(file_path)

        # Run compressor
        output_archive = os.path.join(OUTPUT_FOLDER, f'compressed_{Path(job_folder).name}.dcv')
        
        cmd = [
            sys.executable,
            get_compressor_script(),
            'compress',
            '--root', job_folder,
            '--out', output_archive,
            '--crf', quality
        ]
        
        if lossless:
            cmd.append('--lossless')

        env = os.environ.copy()
        env['PATH'] = FFMPEG_PATH + os.pathsep + env.get('PATH', '')

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env)
        
        if result.returncode != 0:
            return jsonify({'error': 'Compression failed', 'details': result.stderr}), 500

        # Get file info
        file_size = os.path.getsize(output_archive) / (1024 * 1024)  # MB
        
        # If format is zip, create a zip file from the compressed images
        if output_format == 'zip':
            # Decompress the .dcv to get original files
            temp_decompress_folder = os.path.join(OUTPUT_FOLDER, f'temp_decompress_{Path(job_folder).name}')
            os.makedirs(temp_decompress_folder, exist_ok=True)
            
            decomp_cmd = [
                sys.executable,
                get_compressor_script(),
                'decompress',
                '--archive', output_archive,
                '--out', temp_decompress_folder
            ]
            
            decomp_result = subprocess.run(decomp_cmd, capture_output=True, text=True, timeout=600, env=env)
            
            if decomp_result.returncode == 0:
                # Create zip from decompressed files
                zip_path = output_archive.replace('.dcv', '.zip')
                shutil.make_archive(zip_path.replace('.zip', ''), 'zip', temp_decompress_folder)
                
                # Use zip instead of dcv
                os.remove(output_archive)
                output_archive = zip_path
                file_size = os.path.getsize(output_archive) / (1024 * 1024)
                
                # Cleanup temp folder
                shutil.rmtree(temp_decompress_folder, ignore_errors=True)
        
        # Cleanup
        shutil.rmtree(job_folder, ignore_errors=True)

        return jsonify({
            'status': 'success',
            'message': 'Images compressed successfully',
            'archive': os.path.basename(output_archive),
            'size_mb': round(file_size, 2),
            'download_url': f'/api/download/{os.path.basename(output_archive)}'
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/decompress', methods=['POST'])
def decompress():
    """Decompress a .dcv archive"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if not file or not file.filename.endswith('.dcv'):
            return jsonify({'error': 'File must be a .dcv archive'}), 400

        image_format = normalize_image_format(
            request.form.get('image_format', 'original')
        )

        # Save uploaded archive
        archive_name = secure_filename(file.filename)
        archive_path = os.path.join(UPLOAD_FOLDER, archive_name)
        file.save(archive_path)
        original_sizes = get_archive_original_sizes(archive_path)

        # Create output folder
        output_folder = os.path.join(OUTPUT_FOLDER, f'decompressed_{Path(archive_name).stem}')
        shutil.rmtree(output_folder, ignore_errors=True)
        os.makedirs(output_folder, exist_ok=True)

        # Run decompressor
        cmd = [
            sys.executable,
            get_compressor_script(),
            'decompress',
            '--archive', archive_path,
            '--out', output_folder
        ]

        if image_format == 'original':
            cmd.append('--match-original-size')

        env = os.environ.copy()
        env['PATH'] = FFMPEG_PATH + os.pathsep + env.get('PATH', '')

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env)
        
        if result.returncode != 0:
            return jsonify({'error': 'Decompression failed', 'details': result.stderr}), 500

        convert_decompressed_images(Path(output_folder), image_format)

        # List decompressed image files recursively. Archives preserve the
        # source folder name, so images are usually one level deeper.
        output_folder_name = os.path.basename(output_folder)
        decompressed_files = list_decompressed_files(
            Path(output_folder),
            output_folder_name,
            original_sizes if image_format == 'original' else {}
        )

        return jsonify({
            'status': 'success',
            'message': 'Archive decompressed successfully',
            'files': decompressed_files,
            'count': len(decompressed_files),
            'output_folder': output_folder_name,
            'download_all_url': f'/api/download-folder/{output_folder_name}',
            'image_format': image_format
        }), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<filename>', methods=['GET'])
def download(filename):
    """Download compressed or decompressed files"""
    try:
        file_path = os.path.join(OUTPUT_FOLDER, secure_filename(filename))
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/<folder>', methods=['GET'])
def get_files(folder):
    """Get list of files in a decompressed folder"""
    try:
        folder_name = secure_filename(folder)
        folder_path = get_output_folder(folder_name)
        
        if not folder_path.exists():
            return jsonify({'error': 'Folder not found'}), 404

        files = list_decompressed_files(folder_path, folder_name)

        return jsonify({'files': files}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/preview-file/<folder>/<path:filename>', methods=['GET'])
def preview_file(folder, filename):
    """Preview an individual decompressed image in the browser."""
    try:
        file_path = get_output_file(folder, filename)

        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404

        return send_file(file_path, as_attachment=False)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-file/<folder>/<path:filename>', methods=['GET'])
def download_file(folder, filename):
    """Download individual file from decompressed folder"""
    try:
        file_path = get_output_file(folder, filename)
        
        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404

        return send_file(
            file_path,
            as_attachment=True,
            download_name=file_path.name
        )
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-folder/<folder>', methods=['GET'])
def download_folder(folder):
    """Download all decompressed files as a ZIP archive."""
    try:
        folder_name = secure_filename(folder)
        folder_path = get_output_folder(folder_name)

        if not folder_path.exists():
            return jsonify({'error': 'Folder not found'}), 404

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for file_path in sorted(folder_path.rglob('*')):
                if file_path.is_file():
                    archive.write(
                        file_path,
                        file_path.relative_to(folder_path).as_posix()
                    )

        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'{folder_name}.zip'
        )
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File too large. Maximum size is 500MB'}), 413

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
