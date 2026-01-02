FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg curl \
 && pip install yt-dlp flask

WORKDIR /app
COPY app.py .

CMD ["python", "app.py"]
