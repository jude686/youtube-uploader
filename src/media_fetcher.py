import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests

import config
from src.script_generator import Character, ScenePrompt

logger = logging.getLogger("ParableTales.MediaFetcher")

# Max time to wait for a single Omni clip before cancelling and falling back
OMNI_TIMEOUT_SECONDS = 600

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv"}


def _image_mime(path: Path) -> str:
    ext = path.suffix.lower()
    return {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(ext, "image/png")


class MediaFetcher:
    def __init__(self, pexels_api_key: str = config.PEXELS_API_KEY):
        self.pexels_api_key = pexels_api_key

    def export_prompt_payload(self, scenes: List[ScenePrompt], output_json_path: Path):
        """
        Exports the prompt payload formatted for Google Flow (flow.google)
        and other 3D AI video generators (Veo, Kling, Luma).
        """
        payload_data = []
        flow_copy_paste_lines = []

        for s in scenes:
            payload_data.append({
                "scene": s.scene_number,
                "duration_seconds": s.duration_seconds,
                "prompt": s.final_visual_prompt,
                "voiceover_overlay": s.narration,
                "aspect_ratio": "9:16",
                "notes": "Mouths must remain closed; no character speech."
            })
            flow_copy_paste_lines.append(
                f"[SCENE {s.scene_number} - {s.duration_seconds}s]\n"
                f"Prompt: {s.final_visual_prompt}\n"
                f"Narration: {s.narration}\n"
            )

        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(payload_data, f, indent=2)

        # Also write a convenient txt file for pasting into Google Flow studio (flow.google)
        flow_txt_path = output_json_path.parent / "google_flow_storyboard.txt"
        with open(flow_txt_path, "w", encoding="utf-8") as f:
            f.write("=== GOOGLE FLOW (flow.google) STORYBOARD PROMPTS ===\n\n")
            f.write("\n".join(flow_copy_paste_lines))

        logger.info(f"Saved 3D AI prompt payload to {output_json_path}")
        logger.info(f"Saved Google Flow storyboard prompts to {flow_txt_path}")

    def generate_clip_with_omni(
        self,
        prompt: str,
        output_path: Path,
        model_name: str = config.VIDEO_MODEL
    ) -> bool:
        """
        Programmatically generates an 8s video clip using Google's native multimodal Omni model
        (gemini-omni-1.1-flash) via the official google-genai SDK.
        """
        if not config.GEMINI_API_KEY:
            return False

        try:
            import time
            import base64
            from src.genai_client import make_client

            client = make_client()
            logger.info(f"Calling Google Omni Model ({model_name}) for: '{prompt[:50]}...'")

            # Omni only supports the Interactions API. Run in background mode and poll,
            # since a synchronous call can block for minutes (e.g. silently retrying on quota errors).
            interaction = client.interactions.create(
                model=model_name,
                input=prompt,
                background=True,
                timeout=60,
                response_format={"type": "video", "resolution": "720p", "aspect_ratio": "9:16"},
            )

            deadline = time.time() + OMNI_TIMEOUT_SECONDS
            while interaction.status in ("in_progress", "queued") and time.time() < deadline:
                time.sleep(10)
                interaction = client.interactions.get(interaction.id, timeout=60)

            if interaction.status != "completed" or not interaction.output_video:
                errors = "; ".join(f"{e.code}: {e.message}" for e in (interaction.errors or []))
                logger.warning(
                    f"Google Omni generation did not complete (status={interaction.status}). {errors}"
                )
                if interaction.status in ("in_progress", "queued"):
                    client.interactions.cancel(interaction.id)
                return False

            video_bytes = base64.b64decode(interaction.output_video.data)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(video_bytes)
            logger.info(f"✅ Google Omni video clip saved to {output_path.name}")
            return True
        except Exception as e:
            logger.warning(f"Google Omni API generation unavailable: {e}")

        return False

    def generate_image_with_gemini(
        self,
        prompt: str,
        output_path: Path,
        model_name: str = config.IMAGE_MODEL,
        references: Optional[List[Tuple[str, Path]]] = None
    ) -> bool:
        """
        Generates a single 9:16 still frame for a scene using a Gemini Flash image model.
        references: (character name, portrait path) pairs passed as input images so the
        characters keep the same face, hair and clothing as their portraits.
        """
        if not config.GEMINI_API_KEY:
            return False

        try:
            from src.genai_client import make_client
            from google.genai import types

            client = make_client()
            logger.info(f"Calling Gemini image model ({model_name}) for: '{prompt[:50]}...'")

            contents: list = []
            if references:
                for name, path in references:
                    contents.append(types.Part.from_bytes(data=path.read_bytes(), mime_type=_image_mime(path)))
                labels = ", ".join(f"reference image {i} is {name}" for i, (name, _) in enumerate(references, 1))
                contents.append(
                    f"The reference images are character portraits: {labels}. Draw these exact characters: "
                    "keep each one's face, hair, build, skin tone and clothing identical to their reference. "
                    "Do not copy the portraits' poses or plain backgrounds. Scene: " + prompt
                )
            else:
                contents.append(prompt)

            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(aspect_ratio="9:16"),
                ),
            )
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, "wb") as f:
                        f.write(part.inline_data.data)
                    logger.info(f"✅ Gemini scene image saved to {output_path.name}")
                    return True
            logger.warning("Gemini image model returned no image data")
        except Exception as e:
            logger.warning(f"Gemini image generation unavailable: {e}")

        return False

    def generate_character_portrait(self, character: Character, style: str, output_path: Path) -> bool:
        """Full-body reference portrait of a character, used to keep them consistent across scenes."""
        prompt = (
            f"Character reference portrait of {character.name}: {character.description}. "
            "Full body, standing, facing the camera, neutral expression, plain light-grey studio background, "
            f"even lighting, the whole outfit clearly visible, {config.visual_injection(style)}"
        )
        return self.generate_image_with_gemini(prompt, output_path)

    def generate_scene_image(
        self,
        scene: ScenePrompt,
        output_path: Path,
        portraits: Optional[Dict[str, Path]] = None
    ) -> bool:
        """Scene still from its prompt, using the portraits of the characters in it as references."""
        portraits = portraits or {}
        refs = [(name, portraits[name]) for name in scene.characters if name in portraits and portraits[name].exists()]
        return self.generate_image_with_gemini(scene.final_visual_prompt, output_path, references=refs[:3])

    def generate_character_portraits(
        self,
        characters: List[Character],
        style: str,
        output_dir: Path
    ) -> Dict[str, Path]:
        """Generates a portrait per character; returns name -> path for the ones that succeeded."""
        portraits = {}
        for i, c in enumerate(characters, start=1):
            path = output_dir / f"character_{i:02d}.png"
            if self.generate_character_portrait(c, style, path):
                portraits[c.name] = path
        return portraits

    def animate_image_to_clip(
        self,
        image_path: Path,
        output_path: Path,
        duration: float = 8.0,
        zoom_in: bool = True
    ) -> bool:
        """
        Turns a still image into a vertical clip with a slow Ken Burns zoom,
        so image-based episodes still cut together as stacked 8s scenes.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

        w, h, fps = config.VIDEO_WIDTH, config.VIDEO_HEIGHT, config.VIDEO_FPS
        frames = int(duration * fps)
        # Zoom 1.0 -> 1.15 (or reverse) across the clip, centred on the frame
        zoom_expr = f"1+0.15*on/{frames}" if zoom_in else f"1.15-0.15*on/{frames}"
        vf = (
            # Fill 9:16 and upscale 2x first so zoompan doesn't jitter
            f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,"
            f"crop={w * 2}:{h * 2},"
            f"zoompan=z='{zoom_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={frames}:s={w}x{h}:fps={fps}"
        )
        cmd = [
            ffmpeg_exe, "-y",
            "-loop", "1",
            "-i", str(image_path),
            "-vf", vf,
            "-frames:v", str(frames),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            str(output_path)
        ]

        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
            logger.info(f"Animated still image {image_path.name} -> {output_path.name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to animate image {image_path.name}: {e.stderr.decode(errors='ignore')[-500:]}")
            return False

    def generate_clip_with_veo(
        self,
        prompt: str,
        output_path: Path,
        model_name: str = config.VEO_MODEL,
        start_image: Optional[Path] = None
    ) -> bool:
        """
        Generates an 8s 9:16 clip with Veo on the Google Cloud agent platform (Vertex AI).
        start_image: animate this still (image-to-video) so the clip keeps its characters.
        Calls REST directly: with an express-mode API key the SDK's generate_videos omits the
        project from the path and fails with RESOURCE_PROJECT_INVALID.
        Veo's own audio is off; the pipeline adds the voiceover.
        """
        if not (config.GEMINI_USE_VERTEX and config.GOOGLE_CLOUD_PROJECT):
            logger.warning("Veo needs GEMINI_USE_VERTEX=1 and GOOGLE_CLOUD_PROJECT set in .env")
            return False

        import base64
        import time

        loc = config.GOOGLE_CLOUD_LOCATION
        base = (
            f"https://{loc}-aiplatform.googleapis.com/v1/projects/{config.GOOGLE_CLOUD_PROJECT}"
            f"/locations/{loc}/publishers/google/models/{model_name}"
        )
        params = {"key": config.GEMINI_API_KEY}
        instance = {"prompt": prompt}
        if start_image:
            instance["image"] = {
                "bytesBase64Encoded": base64.b64encode(start_image.read_bytes()).decode(),
                "mimeType": _image_mime(start_image),
            }
        body = {
            "instances": [instance],
            "parameters": {
                "aspectRatio": "9:16",
                "durationSeconds": 8,  # Veo max; the composer loops clips to fit longer scenes
                "resolution": "720p",
                "generateAudio": False,
                "sampleCount": 1,
            },
        }

        try:
            mode = f"animating {start_image.name}" if start_image else "text-to-video"
            logger.info(f"Calling Veo ({model_name}, {mode}) for: '{prompt[:50]}...'")
            r = requests.post(f"{base}:predictLongRunning", params=params, json=body, timeout=60)
            if not r.ok:
                logger.warning(f"Veo request rejected ({r.status_code}): {r.text[:300]}")
                return False
            op_name = r.json()["name"]

            deadline = time.time() + OMNI_TIMEOUT_SECONDS
            while time.time() < deadline:
                time.sleep(10)
                status = requests.post(
                    f"{base}:fetchPredictOperation", params=params,
                    json={"operationName": op_name}, timeout=60
                ).json()
                if not status.get("done"):
                    continue
                if "error" in status:
                    logger.warning(f"Veo generation failed: {status['error']}")
                    return False
                videos = status.get("response", {}).get("videos", [])
                if not videos or not videos[0].get("bytesBase64Encoded"):
                    filtered = status.get("response", {}).get("raiMediaFilteredCount", 0)
                    logger.warning(f"Veo returned no video (safety-filtered: {filtered}). Try rewording the prompt.")
                    return False
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(base64.b64decode(videos[0]["bytesBase64Encoded"]))
                logger.info(f"✅ Veo video clip saved to {output_path.name}")
                return True

            logger.warning(f"Veo generation timed out after {OMNI_TIMEOUT_SECONDS}s")
        except Exception as e:
            logger.warning(f"Veo generation unavailable: {e}")

        return False

    def fetch_clip_from_pexels(self, query: str, output_path: Path, min_duration: float = 8.0) -> bool:
        """Downloads a vertical HD video clip from Pexels matching the query."""
        if not self.pexels_api_key:
            return False

        headers = {"Authorization": self.pexels_api_key}
        url = "https://api.pexels.com/videos/search"
        params = {
            "query": query,
            "orientation": "portrait",
            "per_page": 5,
            "size": "medium"
        }

        try:
            res = requests.get(url, headers=headers, params=params, timeout=15)
            if res.status_code == 200:
                data = res.json()
                videos = data.get("videos", [])
                for video in videos:
                    duration = video.get("duration", 0)
                    if duration >= 5:  # Valid clip
                        # Pick best HD vertical file
                        video_files = video.get("video_files", [])
                        # Sort by height descending
                        video_files.sort(key=lambda x: x.get("height", 0), reverse=True)
                        for vf in video_files:
                            download_url = vf.get("link")
                            if download_url:
                                r = requests.get(download_url, stream=True, timeout=30)
                                if r.status_code == 200:
                                    output_path.parent.mkdir(parents=True, exist_ok=True)
                                    with open(output_path, "wb") as f:
                                        for chunk in r.iter_content(chunk_size=1024 * 1024):
                                            f.write(chunk)
                                    logger.info(f"Downloaded Pexels clip for '{query}' -> {output_path.name}")
                                    return True
        except Exception as e:
            logger.warning(f"Error downloading Pexels clip for '{query}': {e}")

        return False

    def generate_procedural_scene_clip(
        self,
        scene: ScenePrompt,
        output_path: Path,
        duration: float = 8.0
    ):
        """
        Creates a high-contrast cinematic vertical backdrop with animated particle motion
        and scene title card when external clips or AI renderers are not yet hooked up.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

        # Dynamic color palettes based on scene number (Biblical golds, ocean blues, deep night, warm dawn)
        palettes = [
            ("0x1A102F", "0x3D1A5E"),  # Royal purple/gold
            ("0x0B2545", "0x134074"),  # Ocean deep blue
            ("0x1F2421", "0x216869"),  # Storm teal
            ("0x3C1518", "0x69140E"),  # Fiery red/crimson
            ("0x283618", "0x606C38"),  # Olive mount
            ("0x2E1F27", "0x854D27"),  # Sunset gold
        ]
        c1, c2 = palettes[(scene.scene_number - 1) % len(palettes)]

        # FFmpeg filter: Generate 1080x1920 test source with subtle zoom/pan
        # Creates an elegant animated background
        cmd = [
            ffmpeg_exe, "-y",
            "-f", "lavfi",
            "-i", f"color=c={c1}:s={config.VIDEO_WIDTH}x{config.VIDEO_HEIGHT}:d={duration}:r={config.VIDEO_FPS}",
            "-vf", f"noise=alls=15:allf=t+u,drawbox=y=ih-350:color=black@0.4:width=iw:height=350:t=fill",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-t", str(duration),
            str(output_path)
        ]

        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            logger.info(f"Generated procedural 8s scene clip {scene.scene_number} -> {output_path.name}")
        except Exception as e:
            logger.error(f"Failed to generate procedural clip: {e}")

    def acquire_scene_clips(
        self,
        scenes: List[ScenePrompt],
        output_dir: Path,
        use_omni: bool = False,
        use_veo: bool = False,
        use_images: bool = False,
        scene_assets: Optional[List[Path]] = None,
        scene_veo: Optional[List[bool]] = None,
        portraits: Optional[Dict[str, Path]] = None
    ) -> List[Path]:
        """
        Gathers or generates an 8-second video clip for every scene in the payload.
        If scene_assets (images/videos per scene, in order) is given, those are used
        exclusively, cycling if the script has more scenes than files. scene_veo[i] = True
        animates that scene's image with Veo (image-to-video) instead of a slow zoom.
        Otherwise, priority:
        1. Local pre-rendered AI clip in `assets/scenes/scene_{n}.mp4`
        2. Local still image in `assets/scenes/scene_{n}.png/.jpg` (animated with Ken Burns zoom)
        3. Veo generation (if use_veo=True; animates a portrait-consistent scene image when
           character portraits are given)
        4. Google Omni Model generation (if use_omni=True and GEMINI_API_KEY is active)
        5. Gemini Flash image (using character portraits) + Ken Burns zoom (if use_images=True)
        6. Pexels Stock API search
        7. Procedural cinematic backdrop
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        clip_paths = []

        if scene_assets:
            for i, s in enumerate(scenes):
                asset = scene_assets[i % len(scene_assets)]
                if asset.suffix.lower() in VIDEO_EXTENSIONS:
                    logger.info(f"Using uploaded clip for scene {s.scene_number}: {asset.name}")
                    clip_paths.append(asset)
                    continue
                scene_file = output_dir / f"scene_{s.scene_number:02d}.mp4"
                if scene_veo and i < len(scene_veo) and scene_veo[i]:
                    if self.generate_clip_with_veo(s.final_visual_prompt, scene_file, start_image=asset):
                        clip_paths.append(scene_file)
                        continue
                    logger.warning(f"Veo failed for scene {s.scene_number}; using a slow zoom of its image instead")
                zoom_in = s.scene_number % 2 == 1
                if not self.animate_image_to_clip(asset, scene_file, s.duration_seconds, zoom_in):
                    raise RuntimeError(f"Could not process image '{asset.name}' for scene {s.scene_number}")
                clip_paths.append(scene_file)
            return clip_paths

        for s in scenes:
            scene_file = output_dir / f"scene_{s.scene_number:02d}.mp4"
            local_asset = config.ASSETS_DIR / "scenes" / f"scene_{s.scene_number:02d}.mp4"

            if local_asset.exists():
                logger.info(f"Using local pre-rendered AI clip: {local_asset}")
                clip_paths.append(local_asset)
                continue

            acquired = False
            zoom_in = s.scene_number % 2 == 1  # alternate zoom direction between scenes

            local_image = next(
                (p for ext in sorted(IMAGE_EXTENSIONS)
                 if (p := local_asset.with_suffix(ext)).exists()),
                None
            )
            if local_image:
                logger.info(f"Using local still image: {local_image}")
                acquired = self.animate_image_to_clip(local_image, scene_file, s.duration_seconds, zoom_in)

            # Try Veo (Google Cloud agent platform) if requested. With character portraits,
            # first make a consistent scene image and animate that.
            if not acquired and use_veo:
                start_image = None
                if portraits:
                    image_file = output_dir / f"scene_{s.scene_number:02d}.png"
                    if self.generate_scene_image(s, image_file, portraits):
                        start_image = image_file
                acquired = self.generate_clip_with_veo(s.final_visual_prompt, scene_file, start_image=start_image)

            # Try Google Omni Model if requested
            if not acquired and use_omni:
                acquired = self.generate_clip_with_omni(s.final_visual_prompt, scene_file)

            # Try Gemini Flash still image, animated into a clip
            if not acquired and use_images:
                image_file = output_dir / f"scene_{s.scene_number:02d}.png"
                if self.generate_scene_image(s, image_file, portraits):
                    acquired = self.animate_image_to_clip(image_file, scene_file, s.duration_seconds, zoom_in)

            # Try Pexels if Veo was not used or failed
            if not acquired and self.pexels_api_key:
                acquired = self.fetch_clip_from_pexels(
                    s.b_roll_search_keyword,
                    scene_file,
                    min_duration=s.duration_seconds
                )

            if not acquired and not scene_file.exists():
                # Fallback to procedural generator
                self.generate_procedural_scene_clip(s, scene_file, duration=s.duration_seconds)

            clip_paths.append(scene_file)

        return clip_paths


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from src.script_generator import generate_fallback_script
    fetcher = MediaFetcher()
    payload = generate_fallback_script("Jonah")
    fetcher.export_prompt_payload(payload.scenes, config.OUTPUT_DIR / "prompts_payload.json")
    clips = fetcher.acquire_scene_clips(payload.scenes[:2], config.OUTPUT_DIR / "temp_scenes")
    print(f"Acquired clips: {clips}")
