from flask import Flask, request, jsonify, send_file
import subprocess
import os
import uuid
import zipfile

app = Flask(__name__)

# Petite page simple pour coller un lien à la main (optionnel)
HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>YouTube → Captures (ZIP)</title>
  <style>
    body{font-family:Arial;margin:40px;max-width:760px}
    input,button{padding:12px;font-size:16px;width:100%;box-sizing:border-box}
    button{margin-top:12px;cursor:pointer}
    small{color:#666}
    code{background:#f4f4f4;padding:2px 6px;border-radius:6px}
  </style>
</head>
<body>
  <h2>YouTube → Captures (transitions) → ZIP</h2>
  <form method="POST" action="/process-zip">
    <label>URL YouTube</label>
    <input name="youtube_url" placeholder="https://www.youtube.com/watch?v=..." required />
    <label style="margin-top:12px;display:block;">Seuil transitions (optionnel)</label>
    <input name="scene_threshold" placeholder="0.30" />
    <button type="submit">Générer et télécharger le ZIP</button>
  </form>
  <p><small>Astuce: tu peux aussi appeler l'API en POST JSON sur <code>/process-zip</code>.</small></p>
</body>
</html>
"""

def to_float(value, default=0.30):
    try:
        return float(value)
    except Exception:
        return default

@app.get("/")
def home():
    return HTML

@app.post("/process-zip")
def process_zip():
    """
    Accepte:
      - form-urlencoded (depuis la page HTML ou n8n)
      - ou JSON: {"youtube_url": "...", "scene_threshold": 0.30}
    Renvoie:
      - un fichier captures.zip en téléchargement
    """
    payload = request.get_json(silent=True) or {}

    youtube_url = request.form.get("youtube_url") or payload.get("youtube_url")
    scene_threshold = request.form.get("scene_threshold") or payload.get("scene_threshold")

    if not youtube_url:
        return jsonify({"error": "youtube_url manquant"}), 400

    scene_threshold = to_float(scene_threshold, 0.30)

    # Dossiers temporaires (Render autorise /tmp)
    uid = str(uuid.uuid4())[:8]
    base = f"/tmp/{uid}"
    os.makedirs(base, exist_ok=True)

    video_path = f"{base}/video.mp4"
    out_dir = f"{base}/captures"
    os.makedirs(out_dir, exist_ok=True)

    try:
        # 1) Télécharger vidéo (mp4)
        subprocess.run(
            [
                "yt-dlp",
                "-f", "bv*+ba/best",
                "--merge-output-format", "mp4",
                "--no-playlist",
                "-o", video_path,
                youtube_url,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # 2) Extraire captures à chaque transition (scene change)
        # Le filtre "scene" détecte les changements visuels.
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-y",
                "-i", video_path,
                "-vf", f"select=gt(scene\\,{scene_threshold})",
                "-vsync", "vfr",
                f"{out_dir}/cap_%04d.jpg",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # 3) Zipper
        zip_path = f"{base}/captures.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for fname in sorted(os.listdir(out_dir)):
                full = os.path.join(out_dir, fname)
                if os.path.isfile(full):
                    z.write(full, arcname=fname)

        # 4) Retourner le ZIP
        return send_file(
            zip_path,
            as_attachment=True,
            download_name="captures.zip",
            mimetype="application/zip",
        )

    except subprocess.CalledProcessError as e:
        # En cas d'erreur, on remonte stderr (utile pour debug)
        err = ""
        try:
            err = (e.stderr or b"").decode("utf-8", errors="ignore")[-2000:]
        except Exception:
            err = "Erreur subprocess (impossible de lire stderr)"
        return jsonify({
            "error": "Échec traitement vidéo",
            "details": err,
            "scene_threshold": scene_threshold
        }), 500

    finally:
        # Nettoyage léger (optionnel)
        # On laisse /tmp se gérer, mais on peut supprimer pour éviter la saturation.
        pass


# OBLIGATOIRE POUR RENDER
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
