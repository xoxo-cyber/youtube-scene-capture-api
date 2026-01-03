FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg curl nodejs npm \
 && ln -s /usr/bin/nodejs /usr/bin/node \
 && pip install --no-cache-dir yt-dlp yt-dlp-ejs flask

WORKDIR /app
COPY app.py .

CMD ["python", "app.py"]
