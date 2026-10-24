"""
Parable Tales web uploader.

Upload ordered scene images/clips + a topic; the server writes the script, records the
voiceover, renders the Short and (optionally) uploads it to YouTube.

Run locally:  uvicorn src.web:app --port 8000
"""
import logging
import queue
import secrets
import shutil
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

import config
from src.media_fetcher import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from src.pipeline import run_pipeline

logger = logging.getLogger("ParableTales.Web")

UPLOADS_DIR = config.OUTPUT_DIR / "uploads"
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # per file
MAX_LOG_LINES = 200

app = FastAPI(title="Parable Tales")
security = HTTPBasic()

# In-memory job store: one instance, one render at a time. Jobs are lost on restart.
jobs: Dict[str, dict] = {}
job_queue: "queue.Queue[str]" = queue.Queue()


def require_password(credentials: HTTPBasicCredentials = Depends(security)):
    if not config.APP_PASSWORD:
        raise HTTPException(503, "APP_PASSWORD is not set on the server")
    if not secrets.compare_digest(credentials.password.encode(), config.APP_PASSWORD.encode()):
        raise HTTPException(401, "Wrong password", headers={"WWW-Authenticate": "Basic"})


# --------------------------------------------------------
# Background worker
# --------------------------------------------------------
class JobLogHandler(logging.Handler):
    """Copies log lines emitted on the worker thread into the active job's log."""

    def __init__(self):
        super().__init__(level=logging.INFO)
        self.current_job: Optional[str] = None

    def emit(self, record: logging.LogRecord):
        if self.current_job and threading.current_thread().name == "render-worker":
            log = jobs[self.current_job]["log"]
            log.append(record.getMessage().strip())
            del log[:-MAX_LOG_LINES]


job_log_handler = JobLogHandler()
logging.getLogger().addHandler(job_log_handler)


def worker():
    while True:
        job_id = job_queue.get()
        job = jobs[job_id]
        job_log_handler.current_job = job_id
        job["status"] = "running"
        job["started"] = time.time()
        try:
            result = run_pipeline(
                topic=job["topic"],
                upload=job["upload"],
                dry_run=not job["upload"],
                voice=job["voice"],
                privacy=job["privacy"],
                scene_assets=[Path(p) for p in job["files"]],
                strict_upload=True,
            )
            job["video_path"] = result["video_path"]
            job["title"] = result["payload"]["title"]
            if job["upload"]:
                job["youtube_url"] = result["upload_result"]["url"]
            job["status"] = "done"
        except Exception as e:
            logger.error(traceback.format_exc())
            job["status"] = "failed"
            job["error"] = str(e) or type(e).__name__
        finally:
            job["finished"] = time.time()
            job_log_handler.current_job = None
            shutil.rmtree(UPLOADS_DIR / job_id, ignore_errors=True)
            job_queue.task_done()


threading.Thread(target=worker, name="render-worker", daemon=True).start()


# --------------------------------------------------------
# Routes
# --------------------------------------------------------
@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/", response_class=HTMLResponse, dependencies=[Depends(require_password)])
def index():
    return INDEX_HTML.replace("{{MAX_SCENES}}", str(config.MAX_SCENES)).replace(
        "{{DEFAULT_PRIVACY}}", config.YOUTUBE_DEFAULT_PRIVACY
    )


@app.post("/jobs", dependencies=[Depends(require_password)])
async def create_job(
    topic: str = Form(...),
    voice: str = Form(config.DEFAULT_VOICE),
    privacy: str = Form(config.YOUTUBE_DEFAULT_PRIVACY),
    upload: bool = Form(False),
    files: List[UploadFile] = File(...),
):
    topic = topic.strip()
    if not topic:
        raise HTTPException(400, "Topic is required")
    if privacy not in ("private", "unlisted", "public"):
        raise HTTPException(400, "Invalid privacy setting")
    if not 1 <= len(files) <= config.MAX_SCENES:
        raise HTTPException(400, f"Upload between 1 and {config.MAX_SCENES} scene files")

    allowed = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
    for f in files:
        if Path(f.filename or "").suffix.lower() not in allowed:
            raise HTTPException(400, f"Unsupported file type: {f.filename}")

    job_id = uuid.uuid4().hex[:12]
    job_dir = UPLOADS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Scenes play in the order the files were sent (the page sends them sorted by name)
    saved = []
    for i, f in enumerate(files, start=1):
        dest = job_dir / f"scene_{i:02d}{Path(f.filename).suffix.lower()}"
        size = 0
        with open(dest, "wb") as out:
            while chunk := await f.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    shutil.rmtree(job_dir, ignore_errors=True)
                    raise HTTPException(413, f"{f.filename} is larger than 200MB")
                out.write(chunk)
        saved.append(str(dest))

    jobs[job_id] = {
        "id": job_id,
        "status": "queued",
        "topic": topic,
        "voice": voice,
        "privacy": privacy,
        "upload": upload,
        "files": saved,
        "created": time.time(),
        "log": [],
    }
    job_queue.put(job_id)
    return {"id": job_id}


@app.get("/jobs/{job_id}", dependencies=[Depends(require_password)])
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found (the server may have restarted)")
    queued_ahead = sum(1 for j in jobs.values() if j["status"] == "queued" and j["created"] < job["created"])
    return {
        "id": job_id,
        "status": job["status"],
        "queued_ahead": queued_ahead,
        "title": job.get("title"),
        "youtube_url": job.get("youtube_url"),
        "has_video": bool(job.get("video_path")),
        "error": job.get("error"),
        "log": job["log"][-40:],
    }


@app.get("/jobs/{job_id}/video", dependencies=[Depends(require_password)])
def get_video(job_id: str):
    job = jobs.get(job_id)
    if not job or not job.get("video_path") or not Path(job["video_path"]).exists():
        raise HTTPException(404, "Video not available")
    return FileResponse(job["video_path"], media_type="video/mp4", filename=f"parable_tales_{job_id}.mp4")


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Parable Tales Studio</title>
<style>
  :root { --bg:#faf8f4; --card:#fff; --ink:#1d1a16; --muted:#6b645a; --line:#e6e0d6; --accent:#7a4dd8; --ok:#1f8a4c; --bad:#c0392b; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#16141a; --card:#201d25; --ink:#f1ede6; --muted:#a49d92; --line:#352f3d; --accent:#a580f0; --ok:#4cc184; --bad:#ef6f61; }
  }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--ink); font:16px/1.5 system-ui, -apple-system, Segoe UI, sans-serif; }
  main { max-width:640px; margin:0 auto; padding:32px 16px 64px; }
  h1 { font-size:24px; margin:0 0 4px; }
  p.sub { color:var(--muted); margin:0 0 24px; }
  form, .card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:20px; }
  label { display:block; font-weight:600; font-size:14px; margin:16px 0 6px; }
  label:first-child { margin-top:0; }
  input[type=text], select { width:100%; padding:10px 12px; border:1px solid var(--line); border-radius:8px; background:var(--bg); color:var(--ink); font:inherit; }
  input[type=file] { width:100%; }
  .row { display:flex; gap:12px; } .row > div { flex:1; min-width:0; }
  .check { display:flex; align-items:center; gap:8px; font-weight:400; margin-top:16px; }
  .hint { color:var(--muted); font-size:13px; margin-top:6px; }
  ol#preview { margin:10px 0 0; padding-left:22px; font-size:14px; color:var(--muted); }
  button { margin-top:20px; width:100%; padding:12px; border:0; border-radius:8px; background:var(--accent); color:#fff; font:600 16px system-ui, sans-serif; cursor:pointer; }
  button:disabled { opacity:.5; cursor:default; }
  .card { margin-top:20px; display:none; }
  .status { font-weight:600; }
  .status.done { color:var(--ok); } .status.failed { color:var(--bad); }
  pre { background:var(--bg); border:1px solid var(--line); border-radius:8px; padding:10px; font-size:12px; max-height:260px; overflow:auto; white-space:pre-wrap; word-break:break-word; }
  a { color:var(--accent); }
</style>
</head>
<body>
<main>
  <h1>Parable Tales Studio</h1>
  <p class="sub">Upload your scenes in order. The script, voiceover, subtitles and render are done for you.</p>

  <form id="f">
    <label for="topic">Bible story / topic</label>
    <input type="text" id="topic" name="topic" required placeholder="e.g. David vs Goliath">

    <label for="files">Scene images or clips</label>
    <input type="file" id="files" name="files" multiple required accept=".png,.jpg,.jpeg,.webp,.mp4,.mov,.webm,.mkv">
    <div class="hint">Up to {{MAX_SCENES}} files, each about 8 seconds of the video. Played in filename order, so name them 01, 02, 03&hellip;</div>
    <ol id="preview"></ol>

    <div class="row">
      <div>
        <label for="voice">Narrator voice</label>
        <select id="voice" name="voice">
          <option value="en-US-ChristopherNeural">Christopher (US)</option>
          <option value="en-US-GuyNeural">Guy (US)</option>
          <option value="en-NG-AbeoNeural">Abeo (Nigeria)</option>
          <option value="en-NG-EzinneNeural">Ezinne (Nigeria)</option>
        </select>
      </div>
      <div>
        <label for="privacy">YouTube privacy</label>
        <select id="privacy" name="privacy">
          <option value="private">Private</option>
          <option value="unlisted">Unlisted</option>
          <option value="public">Public</option>
        </select>
      </div>
    </div>

    <label class="check"><input type="checkbox" id="upload" name="upload" value="true" checked> Upload to YouTube when finished</label>
    <button id="go" type="submit">Generate video</button>
  </form>

  <div class="card" id="job">
    <div class="status" id="status"></div>
    <div id="links"></div>
    <pre id="log"></pre>
  </div>
</main>
<script>
  const $ = id => document.getElementById(id);
  $("privacy").value = "{{DEFAULT_PRIVACY}}";
  const sortedFiles = () => [...$("files").files].sort((a, b) => a.name.localeCompare(b.name, undefined, {numeric: true}));

  $("files").addEventListener("change", () => {
    $("preview").innerHTML = "";
    for (const f of sortedFiles()) {
      const li = document.createElement("li");
      li.textContent = f.name;
      $("preview").appendChild(li);
    }
  });

  $("f").addEventListener("submit", async e => {
    e.preventDefault();
    const data = new FormData();
    data.append("topic", $("topic").value);
    data.append("voice", $("voice").value);
    data.append("privacy", $("privacy").value);
    data.append("upload", $("upload").checked ? "true" : "false");
    for (const f of sortedFiles()) data.append("files", f, f.name);

    $("go").disabled = true;
    $("job").style.display = "block";
    $("links").innerHTML = "";
    $("log").textContent = "";
    show("Uploading files…", "");
    try {
      const r = await fetch("/jobs", { method: "POST", body: data });
      const body = await r.json();
      if (!r.ok) throw new Error(body.detail || r.statusText);
      poll(body.id);
    } catch (err) {
      show("Failed: " + err.message, "failed");
      $("go").disabled = false;
    }
  });

  function show(text, cls) { $("status").textContent = text; $("status").className = "status " + cls; }

  async function poll(id) {
    let j;
    try {
      const r = await fetch("/jobs/" + id);
      j = await r.json();
      if (!r.ok) throw new Error(j.detail || r.statusText);
    } catch (err) {
      show("Lost track of job: " + err.message, "failed");
      $("go").disabled = false;
      return;
    }
    $("log").textContent = j.log.join("\\n");
    $("log").scrollTop = $("log").scrollHeight;
    if (j.status === "queued") show(`Queued (${j.queued_ahead} ahead)…`, "");
    else if (j.status === "running") show("Rendering… this usually takes a few minutes", "");
    else {
      $("go").disabled = false;
      if (j.status === "done") {
        show("Done: " + (j.title || ""), "done");
        let html = "";
        if (j.youtube_url) html += `<p><a href="${j.youtube_url}" target="_blank" rel="noopener">Open on YouTube</a></p>`;
        if (j.has_video) html += `<p><a href="/jobs/${id}/video">Download MP4</a></p>`;
        $("links").innerHTML = html;
      } else {
        show("Failed: " + j.error, "failed");
        if (j.has_video) $("links").innerHTML = `<p><a href="/jobs/${id}/video">Download the rendered MP4</a></p>`;
      }
      return;
    }
    setTimeout(() => poll(id), 3000);
  }
</script>
</body>
</html>
"""
