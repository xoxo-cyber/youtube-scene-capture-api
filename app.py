from flask import Flask, request, jsonify, send_file
import subprocess, os, uuid, zipfile

app = Flask(__name__)

HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>YouTube → Captures (ZIP)</title>
  <style>
    body{font-family:Arial;margin:40px;max-width:820px}
    input,textarea,button{padding:12px;font-size:16px;width:100%;box-sizing:border-box}
    button{margin-top:12px;cursor:pointer}
    label{display:block;margin-top:12px}
    small{color:#666}
  </style>
</head>
<body>
  <h2>YouTube → Captures (transitions) → ZIP</h2>

  <form method="POST" action="/process-zip">
    <label>URL YouTube</label>
    <input name="youtube_url" placeholder="https://www.youtube.com/watch?v=..." required />

    <label>Seuil transitions (optionnel)</label>
    <input name="scene_threshold" placeholder="0.30" />

    <label>Cookies YouTube (optionnel, cookies.txt)</label>
    <textarea name="cookies_txt" rows="6" placeholder="Colle ici le contenu de cookies.txt si YouTube bloque..."></textarea>

    <button type="submit">Générer et télécharger captures.zip</button>
    <p><small>Note: en plan gratuit, le 1er lancement peut être lent (serveur en veille).</small></p>
  </form>
</body>
</html>
"""

def to_float(v, d=0.30):
    try:
        return float(v)
    except:
        return d

@app.get("/")
def home():
    return HTML

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
        # yt-dlp avec "throttle" pour limiter les 429
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

        # extraire scènes
        subprocess.run([
            "ffmpeg", "-hide_banner", "-y", "-i", video,
            "-vf", f"select=gt(scene\\,{scene_threshold})",
            "-vsync", "vfr",
            f"{out}/cap_%04d.jpg"
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # zip
        zip_path = f"{base}/captures.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for fname in sorted(os.listdir(out)):
                full = os.path.join(out, fname)
                if os.path.isfile(full):
                    z.write(full, arcname=fname)

        return send_file(
            zip_path,
            as_attachment=True,
            download_name="captures.zip",
            mimetype="application/zip",
        )

    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode("utf-8", errors="ignore")[-2000:]
        return jsonify({"error": "Échec traitement vidéo", "details": err}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
