from flask import Flask, request, jsonify
import subprocess, os, uuid, re

app = Flask(__name__)

def slugify(text):
    return re.sub(r'[^a-zA-Z0-9]+', '_', text).strip('_').lower()

@app.route("/process", methods=["POST"])
def process():
    data = request.json
    url = data.get("youtube_url")

    if not url:
        return jsonify({"error": "youtube_url manquant"}), 400

    uid = str(uuid.uuid4())[:8]
    base = f"/tmp/{uid}"
    os.makedirs(base, exist_ok=True)

    video = f"{base}/video.mp4"
    out = f"{base}/captures"
    os.makedirs(out, exist_ok=True)

    subprocess.run([
        "yt-dlp", "-f", "bv*+ba/best",
        "--merge-output-format", "mp4",
        "-o", video, url
    ], check=True)

    subprocess.run([
        "ffmpeg", "-i", video,
        "-vf", "select=gt(scene\\,0.30)",
        "-vsync", "vfr",
        f"{out}/cap_%04d.jpg"
    ], check=True)

    images = sorted(os.listdir(out))

    return jsonify({
        "success": True,
        "captures": images,
        "count": len(images)
    })

# 🔥 OBLIGATOIRE POUR RENDER
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
