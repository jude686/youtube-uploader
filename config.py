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

# Visual Prompt Injection
# Automatically appended to every scene prompt sent to video generation APIs
VISUAL_PROMPT_INJECTION = "3D cinematic comic style. No one is speaking; mouths are completely closed"

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

# AI Image Generation Model (for --use-images: still frames animated into 8s Ken Burns clips)
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gemini-3.1-flash-image")

# API Keys & Credentials
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
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
