from flask import Flask, request, render_template, Response, stream_with_context, send_from_directory
import subprocess
import os
import re

app = Flask(__name__)
DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

YOUTUBE_URL_REGEX = r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+'

# Store current download info (naive in-memory, single user)
current_process = None

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/start_download', methods=['POST'])
def start_download():
    global current_process

    url = request.form.get('url', '').strip()
    download_type = request.form.get('format', 'audio')

    if not url:
        return "No URL provided", 400
    if not re.match(YOUTUBE_URL_REGEX, url):
        return "Invalid YouTube URL", 400

    if current_process and current_process.poll() is None:
        return "Another download is in progress. Please wait.", 429

    if download_type == 'audio':
        command = [
            "yt-dlp",
            "-x", "--audio-format", "mp3",
            "--newline",
            "-o", f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
            url
        ]
    else:
        command = [
            "yt-dlp",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
            "--newline",
            "-o", f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
            url
        ]

    current_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return "Download started", 200


def generate_progress():
    global current_process

    if not current_process:
        yield "data: ERROR::No download in progress\n\n"
        return

    for line in iter(current_process.stdout.readline, ''):
        if line.startswith('[download]'):
            yield f"data: {line.strip()}\n\n"

    current_process.stdout.close()
    current_process.wait()

    ext = "mp3" if "-x" in current_process.args else "mp4"
    files = sorted(
        (f for f in os.listdir(DOWNLOAD_DIR) if f.endswith(ext)),
        key=lambda x: os.path.getmtime(os.path.join(DOWNLOAD_DIR, x))
    )

    if files:
        yield f"data: DOWNLOAD_COMPLETE::{files[-1]}\n\n"
    else:
        yield "data: ERROR::No file found\n\n"


@app.route('/progress')
def progress():
    return Response(stream_with_context(generate_progress()), mimetype='text/event-stream')


@app.route('/downloads/<filename>')
def downloads(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True)
