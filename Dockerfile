FROM python:3.11-slim

RUN apt-get update \
 && apt-get install -y ffmpeg curl nodejs npm ca-certificates \
 && (ln -sf /usr/bin/nodejs /usr/bin/node || true) \
 && pip install --no-cache-dir yt-dlp flask \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY app.py .

CMD ["python", "app.py"]
