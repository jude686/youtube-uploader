"""
Parable Tales web studio.

1. Write the script (with a character sheet) for a topic.
2. Make character portraits, then scene images that reuse them (or upload your own).
3. Render: voiceover, slow-zoom or Veo-animated scenes, subtitles, optional YouTube upload.

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
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

import config
from src.media_fetcher import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, MediaFetcher
from src.pipeline import run_pipeline
from src.script_generator import (
    ScenePrompt, ScriptGenerationError, VideoPayload, generate_script_with_gemini, rebuild_scene_prompts
)

logger = logging.getLogger("ParableTales.Web")

UPLOADS_DIR = config.OUTPUT_DIR / "uploads"
SCRIPTS_DIR = config.OUTPUT_DIR / "scripts"
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # per file
MAX_LOG_LINES = 200
INDEX_HTML = (Path(__file__).parent / "templates" / "index.html").read_text(encoding="utf-8")

app = FastAPI(title="Parable Tales")
security = HTTPBasic()

# In-memory stores: one instance, one render at a time. Both are lost on restart.
jobs: Dict[str, dict] = {}
# script_id -> {"topic", "style", "payload" (VideoPayload dict), "dir",
#               "portraits": {char index: path}, "scene_images": {scene index: path}}
scripts: Dict[str, dict] = {}
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
                scene_veo=job.get("veo"),
                strict_upload=True,
                # Fresh copy each run: the pipeline adjusts scene durations in place
                payload=VideoPayload(**job["payload"]) if job.get("payload") else None,
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
    veo_enabled = config.GEMINI_USE_VERTEX and bool(config.GOOGLE_CLOUD_PROJECT)
    return (
        INDEX_HTML.replace("{{MAX_SCENES}}", str(config.MAX_SCENES))
        .replace("{{DEFAULT_PRIVACY}}", config.YOUTUBE_DEFAULT_PRIVACY)
        .replace("{{VEO_ENABLED}}", "true" if veo_enabled else "false")
        .replace("{{STYLE_OPTIONS}}", "".join(
            f'<option value="{key}"{" selected" if key == config.DEFAULT_VISUAL_STYLE else ""}>{s["label"]}</option>'
            for key, s in config.VISUAL_STYLES.items()
        ))
    )


def image_prompt(scene: ScenePrompt) -> str:
    """Scene prompt adapted for image generators (Gemini, Midjourney, Flow, etc.)."""
    return f"Vertical 9:16 portrait image. {scene.final_visual_prompt}"


@app.post("/scripts", dependencies=[Depends(require_password)])
def create_script(topic: str = Form(...), num_scenes: int = Form(5), style: str = Form(config.DEFAULT_VISUAL_STYLE)):
    """Writes the script first so the user can make scene images from its prompts."""
    topic = topic.strip()
    if not topic:
        raise HTTPException(400, "Topic is required")
    if not 1 <= num_scenes <= config.MAX_SCENES:
        raise HTTPException(400, f"Choose between 1 and {config.MAX_SCENES} scenes")
    if style not in config.VISUAL_STYLES:
        raise HTTPException(400, "Unknown visual style")

    try:
        payload = generate_script_with_gemini(topic, num_scenes=num_scenes, allow_fallback=False, style=style)
    except ScriptGenerationError as e:
        raise HTTPException(503, f"Couldn't write the script right now, try again in a minute. {e}")
    script_id = uuid.uuid4().hex[:12]
    scripts[script_id] = {
        "topic": topic, "style": style, "payload": payload.model_dump(),
        "dir": SCRIPTS_DIR / script_id, "portraits": {}, "scene_images": {},
    }
    return script_view(script_id)


def script_view(script_id: str) -> dict:
    script = scripts[script_id]
    payload = VideoPayload(**script["payload"])
    return {
        "id": script_id,
        "title": payload.title,
        "book_chapter": payload.book_chapter,
        "cta_question": payload.cta_question,
        "style": config.VISUAL_STYLES[payload.style]["label"],
        "characters": [{"name": c.name, "description": c.description} for c in payload.characters],
        "scenes": [
            {"number": s.scene_number, "narration": s.narration, "image_prompt": image_prompt(s),
             "characters": s.characters}
            for s in payload.scenes
        ],
    }


def get_script(script_id: str) -> dict:
    script = scripts.get(script_id)
    if not script:
        raise HTTPException(404, "Script not found (the server may have restarted). Write it again.")
    return script


def file_url(kind: str, script_id: str, index: int) -> str:
    # Cache-buster so the page shows a regenerated image
    return f"/scripts/{script_id}/{kind}/{index}?v={int(time.time() * 1000)}"


async def save_upload(f: UploadFile, dest_stem: Path, allowed: set) -> Path:
    suffix = Path(f.filename or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(400, f"Unsupported file type: {f.filename}")
    dest = dest_stem.with_suffix(suffix)
    dest.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with open(dest, "wb") as out:
        while chunk := await f.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"{f.filename} is larger than 200MB")
            out.write(chunk)
    return dest


@app.post("/scripts/{script_id}/characters/{index}", dependencies=[Depends(require_password)])
def update_character(script_id: str, index: int, description: str = Form(...)):
    """Edits a character's fixed description; every scene prompt that includes them is rebuilt."""
    script = get_script(script_id)
    payload = VideoPayload(**script["payload"])
    if not 0 <= index < len(payload.characters):
        raise HTTPException(404, "No such character")
    payload.characters[index].description = description.strip().rstrip(".")
    rebuild_scene_prompts(payload)
    script["payload"] = payload.model_dump()
    return script_view(script_id)


@app.post("/scripts/{script_id}/characters/{index}/portrait", dependencies=[Depends(require_password)])
async def make_portrait(script_id: str, index: int, file: Optional[UploadFile] = File(None)):
    """Generates a character portrait, or stores an uploaded one."""
    script = get_script(script_id)
    payload = VideoPayload(**script["payload"])
    if not 0 <= index < len(payload.characters):
        raise HTTPException(404, "No such character")
    stem = script["dir"] / "characters" / f"character_{index + 1:02d}_{uuid.uuid4().hex[:6]}"
    if file is not None and file.filename:
        path = await save_upload(file, stem, IMAGE_EXTENSIONS)
    else:
        path = stem.with_suffix(".png")
        ok = await run_in_threadpool(
            MediaFetcher().generate_character_portrait, payload.characters[index], payload.style, path
        )
        if not ok:
            raise HTTPException(502, "The image model didn't return a portrait. Try again.")
    script["portraits"][index] = str(path)
    return {"url": file_url("characters", script_id, index)}


@app.post("/scripts/{script_id}/scenes/{index}/image", dependencies=[Depends(require_password)])
def make_scene_image(script_id: str, index: int):
    """Generates a scene image that reuses the character portraits as references."""
    script = get_script(script_id)
    payload = VideoPayload(**script["payload"])
    if not 0 <= index < len(payload.scenes):
        raise HTTPException(404, "No such scene")
    portraits = {
        payload.characters[i].name: Path(p) for i, p in script["portraits"].items() if i < len(payload.characters)
    }
    path = script["dir"] / "scenes" / f"scene_{index + 1:02d}_{uuid.uuid4().hex[:6]}.png"
    if not MediaFetcher().generate_scene_image(payload.scenes[index], path, portraits):
        raise HTTPException(502, "The image model didn't return an image. Try again.")
    script["scene_images"][index] = str(path)
    return {"url": file_url("scenes", script_id, index)}


@app.get("/scripts/{script_id}/{kind}/{index}", dependencies=[Depends(require_password)])
def get_script_file(script_id: str, kind: str, index: int):
    script = get_script(script_id)
    store = {"characters": script["portraits"], "scenes": script["scene_images"]}.get(kind)
    if store is None or index not in store:
        raise HTTPException(404, "Not generated yet")
    return FileResponse(store[index])


@app.post("/jobs", dependencies=[Depends(require_password)])
async def create_job(
    topic: str = Form(""),
    script_id: str = Form(""),
    voice: str = Form(config.DEFAULT_VOICE),
    privacy: str = Form(config.YOUTUBE_DEFAULT_PRIVACY),
    upload: bool = Form(False),
    # Comma-separated, one per scene: "file" (next uploaded file) or "generated" (the
    # scene image made on the page)
    slots: str = Form(""),
    # Comma-separated 1/0 per scene: animate that scene's image with Veo
    veo: str = Form(""),
    files: List[UploadFile] = File(default=[]),
):
    script = get_script(script_id) if script_id else None
    if script:
        topic = script["topic"]

    slot_list = [x.strip() for x in slots.split(",") if x.strip()] or ["file"] * len(files)
    if any(x not in ("file", "generated") for x in slot_list) or slot_list.count("file") != len(files):
        raise HTTPException(400, "Scene slots don't match the uploaded files")
    if script and len(slot_list) != len(script["payload"]["scenes"]):
        raise HTTPException(400, f"Give every scene an image ({len(script['payload']['scenes'])} scenes)")
    if "generated" in slot_list and not script:
        raise HTTPException(400, "Generated scene images need a written script")
    veo_list = [x.strip() == "1" for x in veo.split(",")] if veo.strip() else [False] * len(slot_list)
    if len(veo_list) != len(slot_list):
        raise HTTPException(400, "Veo choices don't match the scenes")
    if any(veo_list) and not (config.GEMINI_USE_VERTEX and config.GOOGLE_CLOUD_PROJECT):
        raise HTTPException(400, "Veo needs GEMINI_USE_VERTEX=1 and GOOGLE_CLOUD_PROJECT on the server")

    topic = topic.strip()
    if not topic:
        raise HTTPException(400, "Topic is required")
    if privacy not in ("private", "unlisted", "public"):
        raise HTTPException(400, "Invalid privacy setting")
    if not 1 <= len(slot_list) <= config.MAX_SCENES:
        raise HTTPException(400, f"Use between 1 and {config.MAX_SCENES} scenes")

    job_id = uuid.uuid4().hex[:12]
    job_dir = UPLOADS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # One path per scene, in order. Generated images are copied so regenerating on the page
    # doesn't change a queued job.
    saved: List[str] = []
    file_iter = iter(files)
    try:
        for i, slot in enumerate(slot_list):
            stem = job_dir / f"scene_{i + 1:02d}"
            if slot == "generated":
                src = script["scene_images"].get(i)
                if not src or not Path(src).exists():
                    raise HTTPException(400, f"Scene {i + 1} has no generated image yet")
                dest = stem.with_suffix(Path(src).suffix)
                shutil.copy(src, dest)
            else:
                dest = await save_upload(next(file_iter), stem, IMAGE_EXTENSIONS | VIDEO_EXTENSIONS)
            saved.append(str(dest))
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise

    jobs[job_id] = {
        "id": job_id,
        "status": "queued",
        "topic": topic,
        "voice": voice,
        "privacy": privacy,
        "upload": upload,
        "files": saved,
        "veo": veo_list,
        "payload": script["payload"] if script else None,
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
