# Parable Tales: Autonomous YouTube Shorts Pipeline 🎬
> **Niche**: 3D Cinematic Bible Story Animation & Comedy  
> Blending scripturally accurate biblical narratives with modern, relatable storytelling, high-retention cultural humor, and clear faith lessons under the **Parable Tales** brand.

---

## 🌟 Core Content Formula
* **Pacing**: Stacked **8-second AI video clip generations** (`CLIP_DURATION_SECONDS = 8.0`).
* **Audio Architecture**: Charismatic voiceover narrator with **strict constraints against character lip-syncing** (mouths remain closed).
* **Narrative Arc**:
  1. *Modern Hook / Tension* (relatable everyday dilemma or cultural comedy).
  2. *The Biblical Event* (scripturally accurate narrative & high visual drama).
  3. *Practical Life Lesson* (faith-based takeaway).
  4. *Comment-Driving Call to Action* (question prompting viewer engagement).
* **Visual Prompt Injection**: Automatically appends `"3D cinematic comic style. No one is speaking; mouths are completely closed"` to every scene payload.
* **YouTube Title Archetypes**:
  * `[Modern Hook/Curiosity] (Bible Character/Story) #Shorts`
  * `The [Adjective] [Event] in the Bible #Shorts`
* **Default Tag Payload**: `["Bible animation", "3D Bible stories", "Christian comedy", "Parable Tales", "faith lessons", "[Book Chapter]"]`

---

## 📂 Project Architecture

```
prolink/
├── .env.example              # Environment variables template
├── requirements.txt          # Python dependencies
├── config.py                 # Central configuration & brand constants
├── credentials/              # Store client_secret.json & token.json here (gitignored)
├── assets/                   # Fonts, background music, or custom AI clips
├── output/                   # Generated episodes, audio, and prompt payloads
└── src/
    ├── __init__.py
    ├── script_generator.py   # Gemini 1.5 Flash scriptwriter & 8s prompt injector
    ├── voice_engine.py       # edge-tts audio generator & subtitle synchronizer
    ├── media_fetcher.py      # Pexels API, 3D AI prompt export, and procedural backdrops
    ├── video_composer.py     # FFmpeg 9:16 short compositor with styled subtitles
    ├── youtube_uploader.py   # YouTube Data API v3 OAuth2 uploader
    ├── pipeline.py           # Master CLI orchestrator
    └── web.py                # Web Studio (upload scenes → render → YouTube)
```

---

## ⚡ Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment (.env)
Copy `.env.example` to `.env`:
```bash
copy .env.example .env
```
Add your API keys:
* **`GEMINI_API_KEY`**: Free key from [Google AI Studio](https://aistudio.google.com).
* **`PEXELS_API_KEY`** *(Optional)*: Free key from [Pexels](https://www.pexels.com/api/).
* **`YOUTUBE_CLIENT_SECRETS_FILE`**: Path to your Google Cloud OAuth Client Secret (see below).

---

## 🔑 Setting Up YouTube Uploads (One-Time)
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g. `Parable-Tales-Uploader`).
3. Under **APIs & Services > Library**, search for and enable **YouTube Data API v3**.
4. Under **APIs & Services > OAuth consent screen**, select **External**, name your app, and add your own Google email as a **Test User**.
5. Under **APIs & Services > Credentials**, click **Create Credentials > OAuth client ID**, select **Desktop App**, and download the JSON file.
6. Save the downloaded file as `credentials/client_secret.json`.
7. The first time you run with `--upload`, your browser will open to grant permission. Once granted, a permanent `credentials/token.json` is saved so all future uploads are completely autonomous!

---

## 🚀 Running the Pipeline

### Local Dry Run (Test without uploading)
```bash
python -m src.pipeline --topic "Jonah Running from God" --dry-run
```

### Run with Gemini & Upload to YouTube (Private Mode)
```bash
python -m src.pipeline --topic "David vs Goliath" --upload
```

### Using Nigerian English Voice for Cultural Comedy
```bash
python -m src.pipeline --topic "Samson and Delilah" --voice "en-NG-AbeoNeural" --dry-run
```
*(Available voices include `en-US-ChristopherNeural`, `en-US-GuyNeural`, `en-NG-AbeoNeural`, `en-NG-EzinneNeural`)*.

---

## 🎨 Google Omni Model (`gemini-omni-1.1-flash`) & Google Flow

### Option 1: 100% Autonomous Generation with Google Omni Model
The pipeline uses Google's native multimodal **Omni model** (`gemini-omni-1.1-flash` via the `google-genai` SDK) to generate 3D comic scenes programmatically using your same `GEMINI_API_KEY`:
```bash
python -m src.pipeline --topic "David vs Goliath" --use-omni --dry-run
```
*(You can also use `--use-veo` as a backward-compatible alias)*.

### Option 2: Human-in-the-Loop with Google Flow Studio (`flow.google`)
Google Flow's browser studio (`flow.google`) offers **Character Consistency ("Ingredients")**, allowing you to lock in the exact 3D comic character face (e.g., Jonah, Samson, Delilah) across all shots.
1. Run the pipeline to generate your script and 8s scene prompts.
2. The pipeline creates:
   * `output/episode_<timestamp>/google_flow_storyboard.txt`
   * `output/episode_<timestamp>/prompts_payload.json`
3. Paste the prompts into [Google Flow](https://flow.google) and set your character ingredient.
4. Download the generated clips into `assets/scenes/scene_01.mp4`, `scene_02.mp4`, etc.
5. Re-run the pipeline—it will automatically detect the clips in `assets/scenes/`, sync the voiceover, burn styled Parable Tales subtitles, and post to YouTube!

---

## 🖼️ Image Mode (`--use-images`)
Generates one still per scene with Gemini Flash (`IMAGE_MODEL`, default `gemini-3.1-flash-image`) and animates it into a slow-zoom clip:
```bash
python -m src.pipeline --topic "David vs Goliath" --use-images --dry-run
```
Gemini image models need billing enabled (the free tier limit is 0). You can also drop your own stills into `assets/scenes/scene_01.png`, `scene_02.jpg`, … and they are animated automatically.

Scenes stretch to cover the full narration (minimum 8s each), so the voiceover is never cut off.

---

## 🌐 Web Studio (upload scenes → video → YouTube)
A password-protected page where you enter a topic, upload your scene images/clips in order, and the server writes a script with exactly one scene per file, records the voiceover, renders the Short and uploads it to YouTube.

Run locally:
```bash
pip install -r requirements.txt
set APP_PASSWORD=choose-a-password
uvicorn src.web:app --port 8000
```
Open http://localhost:8000 and log in with any username plus `APP_PASSWORD`. Files play in filename order (name them `01.png`, `02.png`, …).

### Deploying to Northflank

**1. Get a long-lived YouTube token (do this first).**
While your Google Cloud OAuth app is in *Testing*, its refresh token expires after 7 days and the server can't log in again by itself.
1. Google Cloud Console → **APIs & Services → OAuth consent screen → Publish app** (verification isn't needed for your own channel; you'll click past an "unverified app" warning).
2. Delete `credentials/token.json`, then re-authorize locally:
   ```bash
   python -c "from src.youtube_uploader import YouTubeUploader; YouTubeUploader().authenticate()"
   ```
   This writes a fresh `credentials/token.json`.

**2. Push the code to a private GitHub repo.** `.gitignore` already keeps `.env`, `credentials/*.json` and `output/` out of git. Never commit them.

**3. Create the service.** In [Northflank](https://app.northflank.com): create a project, then **Create new → Service → Combined service** (builds and deploys from your repo).
- **Repository:** link GitHub and pick your repo and branch.
- **Build type:** Dockerfile (path `/Dockerfile`, build context `/`).
- **Resources:** at least 1 vCPU / 1 GB memory. The smallest plans make renders very slow and FFmpeg can run out of memory.
- **Ports:** port `8000` is detected from the Dockerfile. Set the protocol to HTTP and make it **public** so you get a URL.
- **Health check (optional):** HTTP `GET /healthz` on port 8000.

**4. Runtime variables.** On the service's **Environment** page, add:
| Key | Value |
|---|---|
| `APP_PASSWORD` | a long password of your choice |
| `GEMINI_API_KEY` | your Gemini key |
| `PEXELS_API_KEY` | optional |
| `YOUTUBE_DEFAULT_PRIVACY` | `private` |
| `YOUTUBE_CLIENT_SECRETS_FILE` | `/etc/secrets/client_secret.json` |
| `YOUTUBE_TOKEN_FILE` | `/etc/secrets/token.json` |

**5. Secret files.** On the same Environment page, under secret files, click **add file** twice:
- Mount path `/etc/secrets/client_secret.json`: upload `credentials/client_secret.json`
- Mount path `/etc/secrets/token.json`: upload `credentials/token.json`

Save; the service redeploys.

**6. Use it.** Open the public URL shown under the service's ports, log in with any username plus `APP_PASSWORD`, and generate.

### Hosting notes
- **Instances:** keep the service at **1 instance**. Jobs are tracked in memory, so a second instance wouldn't know about them.
- **One render at a time.** Extra jobs queue. A 3-scene Short takes a few minutes.
- **Nothing is kept.** Jobs and rendered MP4s live in memory/local disk and vanish on redeploy or restart. Download the MP4 or rely on the YouTube upload.
- **YouTube limits:** about 6 uploads/day on the default API quota. Uploads from an unaudited Google Cloud project are locked to **private** until you pass the [YouTube API audit](https://support.google.com/youtube/contact/yt_api_form); until then, make videos public by hand in YouTube Studio.
# youtube-uploader
