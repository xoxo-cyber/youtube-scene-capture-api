from flask import Flask, request, jsonify, send_file
import subprocess, os, uuid, zipfile

app = Flask(__name__)

def to_float(v, d=0.30):
    try:
        return float(v)
    except:
        return d

@app.post("/process-zip")
def process_zip():
    payload = request.get_json(silent=True) or {}
    youtube_url = request.form.get("youtube_url") or payload.get("youtube_url")
    scene_threshold = request.form.get("scene_threshold") or payload.get("scene_threshold")
    cookies_txt = request.form.get("cookies_txt") or payload.get("cookies_txt")

    if not youtube_url:
        return jsonify({"error": "youtube_url manquant"}), 400

    scene_threshold = to_float(scene_threshold, 0.30)

    uid = str(uuid.uuid4())[:8]
    base = f"/tmp/{uid}"
    os.makedirs(base, exist_ok=True)

    video = f"{base}/video.mp4"
    out = f"{base}/captures"
    os.makedirs(out, exist_ok=True)

    cookies_file = None
    if cookies_txt:
        cookies_file = f"{base}/cookies.txt"
        with open(cookies_file, "w", encoding="utf-8") as f:
            f.write(cookies_txt)

    try:
        cmd = [
            "yt-dlp",
            "--sleep-interval", "1",
            "--max-sleep-interval", "3",
            "--concurrent-fragments", "1",
            "--limit-rate", "1M",
            "-f", "bv*+ba/best",
            "--merge-output-format", "mp4",
            "--no-playlist",
            "-o", video,
        ]

        if cookies_file:
            cmd += ["--cookies", cookies_file]

        cmd += [youtube_url]

        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        subprocess.run([
            "ffmpeg", "-y", "-i", video,
            "-vf", f"select=gt(scene\\,{scene_threshold})",
            "-vsync", "vfr",
            f"{out}/cap_%04d.jpg"
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        zip_path = f"{base}/captures.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(os.listdir(out)):
                z.write(os.path.join(out, f), arcname=f)

        return send_file(zip_path, as_attachment=True, download_name="captures.zip")

    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode("utf-8", errors="ignore")[-2000:]
        return jsonify({"error": "yt-dlp/ffmpeg failed", "details": err}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
