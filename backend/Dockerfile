# Image Compressor API — Flask + FFmpeg (libaom-av1) for Render Docker deploy
FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Fail the image build if AV1 encoder is missing (required for compression).
RUN ffmpeg -hide_banner -encoders 2>/dev/null | grep -q libaom-av1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FFMPEG_PATH=/usr/bin \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN mkdir -p uploads/output

EXPOSE 5000

# Render injects PORT; compression can take several minutes.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 1 --threads 2 --timeout 600 app:app"]
