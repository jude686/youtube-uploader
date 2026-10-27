import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ========================================================
# Parable Tales: Niche & Brand Configuration
# ========================================================
BRAND_NAME = "Parable Tales"
NICHE_DESCRIPTION = "3D Cinematic Bible Story Animation & Comedy"

# Strict Pacing Constraint: Stacked 8-second AI video clips
CLIP_DURATION_SECONDS = 8.0

# Visual styles a creator can pick per episode. The style's prompt is appended to every
# scene prompt sent to image/video generators, followed by the closed-mouth constraint.
VISUAL_STYLES = {
    "3d": {
        "label": "3D animated",
        "prompt": "3D animated movie style, Pixar-quality CGI render, cinematic lighting",
    },
    "realistic": {
        "label": "Realistic",
        "prompt": "Photorealistic cinematic live-action style, natural lighting, realistic skin and textures, shot on 35mm film",
    },
    "cartoon": {
        "label": "Cartoon",
        "prompt": "2D cartoon illustration style, bold clean outlines, vibrant flat colors",
    },
}
DEFAULT_VISUAL_STYLE = os.getenv("VISUAL_STYLE", "3d")
MOUTHS_CLOSED = "No one is speaking; mouths are completely closed"


def visual_injection(style: str = DEFAULT_VISUAL_STYLE) -> str:
    """Suffix appended to every scene prompt for the given style key."""
    return f"{VISUAL_STYLES.get(style, VISUAL_STYLES['3d'])['prompt']}. {MOUTHS_CLOSED}"


# Default injection (kept for callers that don't pick a style)
VISUAL_PROMPT_INJECTION = visual_injection()

# Default YouTube Tag Payload
BASE_TAGS = [
    "Bible animation",
    "3D Bible stories",
    "Christian comedy",
    "Parable Tales",
    "faith lessons",
]

# Title Format Archetypes:
# 1. [Modern Hook/Curiosity] (Bible Character/Story)
# 2. The [Adjective] [Event] in the Bible

# Video Specs (YouTube Shorts 9:16)
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30

# Audio / Voice Settings
# Edge-TTS voices:
# - 'en-US-ChristopherNeural' (Deep, charismatic, cinematic narrator)
# - 'en-NG-AbeoNeural' / 'en-NG-EzinneNeural' (Charismatic Nigerian English for cultural comedic delivery)
DEFAULT_VOICE = os.getenv("TTS_VOICE", "en-US-ChristopherNeural")

# AI Video Generation Model
# Default: Google's native multimodal Omni model 'gemini-omni-1.1-flash'
VIDEO_MODEL = os.getenv("VIDEO_MODEL", "gemini-omni-1.1-flash")

# Script-writing models, tried in order until one succeeds (comma-separated in .env).
# Free-tier models are often rate-limited (429) or overloaded (503), so keep several.
# (The "-latest" aliases only exist on AI Studio, not on the Google Cloud agent platform.)
_DEFAULT_SCRIPT_MODELS = (
    "gemini-3.8-flash,gemini-3.5-flash,gemini-3.5-flash-lite"
    if os.getenv("GEMINI_USE_VERTEX", "0") == "1" else
    "gemini-flash-latest,gemini-3.5-flash,gemini-3.8-flash,gemini-3.5-flash-lite,gemini-flash-lite-latest"
)
SCRIPT_MODELS = [m.strip() for m in os.getenv("SCRIPT_MODELS", _DEFAULT_SCRIPT_MODELS).split(",") if m.strip()]
SCRIPT_TIMEOUT_SECONDS = int(os.getenv("SCRIPT_TIMEOUT_SECONDS", "50"))

# AI Image Generation Model (for --use-images: still frames animated into 8s Ken Burns clips)
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gemini-3.1-flash-image")

# API Keys & Credentials
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# 1 = GEMINI_API_KEY is a Google Cloud agent platform (Vertex AI express mode) key,
# billed through Google Cloud instead of AI Studio
GEMINI_USE_VERTEX = os.getenv("GEMINI_USE_VERTEX", "0") == "1"
# Needed for Veo video generation on the agent platform (project number or ID)
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
# veo-3.1-lite-generate-001 (cheapest), veo-3.1-fast-generate-001, veo-3.1-generate-001 (best)
VEO_MODEL = os.getenv("VEO_MODEL", "veo-3.1-lite-generate-001")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
YOUTUBE_CLIENT_SECRETS_FILE = os.getenv(
    "YOUTUBE_CLIENT_SECRETS_FILE", 
    str(BASE_DIR / "credentials" / "client_secret.json")
)
YOUTUBE_TOKEN_FILE = os.getenv(
    "YOUTUBE_TOKEN_FILE",
    str(BASE_DIR / "credentials" / "token.json")
)
YOUTUBE_DEFAULT_PRIVACY = os.getenv("YOUTUBE_DEFAULT_PRIVACY", "private")

# Web app / hosting
# HEADLESS=1 disables the browser OAuth flow (servers must ship a pre-authorized token.json)
HEADLESS = os.getenv("HEADLESS", "0") == "1"
# Password for the web upload page (any username). Required when hosting.
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
MAX_SCENES = int(os.getenv("MAX_SCENES", "10"))

# Paths
OUTPUT_DIR = BASE_DIR / "output"
CREDENTIALS_DIR = BASE_DIR / "credentials"
ASSETS_DIR = BASE_DIR / "assets"
