from flask import Flask, request, jsonify, send_file
import subprocess
import os
import uuid
import zipfile

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

    <label>Cookies YouTube (format Netscape cookies.txt)</label>
    <textarea name="cookies_txt" rows="6"
      placeholder="# Netscape HTTP Cookie File&#10;.youtube.com TRUE / TRUE 2145916800 SID ..."></textarea>

    <button type="submit">Générer et télécharger captures.zip</button>
    <p><small>Le premier lancement peut être lent (serveur en veille).</small></p>
  </form>
</body>
</html>
"""

def to_float(v, default=0.30):
    try:
        return float(v)
    except:
        return default

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

    video_path = f"{base}/video.mp4"
    captures_dir = f"{base}/captures"
    os.makedirs(captures_dir, exist_ok=True)

    cookies_file = None
    if cookies_txt:
        cookies_file = f"{base}/cookies.txt"
        with open(cookies_file, "w", encoding="utf-8") as f:
            f.write(cookies_txt)

    try:
        # 🔴 COMMANDE yt-dlp AVEC --js-runtimes node
        cmd = [
            "yt-dlp",
            "--js-runtimes", "node",
            "--sleep-interval", "1",
            "--max-sleep-interval", "3",
            "--concurrent-fragments", "1",
            "--limit-rate", "1M",
            "-f", "bv*+ba/best",
            "--merge-output-format", "mp4",
            "--no-playlist",
            "-o", video_path,
        ]

        if cookies_file:
            cmd += ["--cookies", cookies_file]

        cmd += [youtube_url]

        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # 🔴 EXTRACTION DES TRANSITIONS (SCENE CHANGE)
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-y",
                "-i", video_path,
                "-vf", f"select=gt(scene\\,{scene_threshold})",
                "-vsync", "vfr",
                f"{captures_dir}/cap_%04d.jpg",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # 🔴 ZIP DES CAPTURES
        zip_path = f"{base}/captures.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for name in sorted(os.listdir(captures_dir)):
                full = os.path.join(captures_dir, name)
                if os.path.isfile(full):
                    z.write(full, arcname=name)

        return send_file(
            zip_path,
            as_attachment=True,
            download_name="captures.zip",
            mimetype="application/zip",
        )

    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode("utf-8", errors="ignore")[-2000:]
        return jsonify({
            "error": "Échec traitement vidéo",
            "details": err
        }), 500


# 🔴 OBLIGATOIRE POUR RENDER
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
