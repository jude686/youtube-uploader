import argparse
import logging
import sys
import time
from pathlib import Path
from typing import List, Optional

import config
from src.script_generator import VideoPayload, generate_script_with_gemini
from src.voice_engine import generate_narration_audio
from src.media_fetcher import MediaFetcher
from src.video_composer import VideoComposer
from src.youtube_uploader import YouTubeUploader, mock_upload_dry_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ParableTales.Pipeline")


def run_pipeline(
    topic: str,
    upload: bool = False,
    dry_run: bool = False,
    use_omni: bool = False,
    use_veo: bool = False,
    use_images: bool = False,
    voice: str = config.DEFAULT_VOICE,
    privacy: str = config.YOUTUBE_DEFAULT_PRIVACY,
    scene_assets: Optional[List[Path]] = None,
    strict_upload: bool = False,
    payload: Optional[VideoPayload] = None,
    style: str = config.DEFAULT_VISUAL_STYLE,
    scene_veo: Optional[List[bool]] = None
):
    """
    scene_assets: user-provided scene images/videos in order; the script is written
                  with exactly one scene per file.
    strict_upload: raise on YouTube upload failure instead of falling back to a dry run.
    payload: a previously generated script to render (skips script generation), e.g. one
             whose image prompts the user already used to make the scene_assets.
    scene_veo: per scene, True to animate that scene's image with Veo instead of a slow zoom.
    """
    start_time = time.time()
    logger.info("=" * 65)
    logger.info(f"🚀 STARTING PIPELINE: '{config.BRAND_NAME}'")
    logger.info(f"🎬 Niche: {config.NICHE_DESCRIPTION}")
    logger.info(f"📖 Topic: {topic}")
    logger.info("=" * 65)

    timestamp = int(time.time())
    episode_dir = config.OUTPUT_DIR / f"episode_{timestamp}"
    episode_dir.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------
    # STEP 1: SCRIPT & VISUAL PROMPT GENERATION
    # ----------------------------------------------------
    if payload:
        logger.info("\n[STEP 1/5] Using the pre-generated script...")
    else:
        logger.info("\n[STEP 1/5] Generating script & 8s scene prompts via Gemini Flash...")
        payload = generate_script_with_gemini(topic, num_scenes=len(scene_assets) if scene_assets else None, style=style)

    logger.info(f"🏷️  Selected Title: {payload.title}")
    logger.info(f"📜 Scripture: {payload.book_chapter}")
    logger.info(f"⏱️  Scenes planned: {len(payload.scenes)} scenes (Stacked {config.CLIP_DURATION_SECONDS}s each)")
    logger.info(f"💬 CTA Question: {payload.cta_question}")

    # Export prompt payload file for 3D AI video generators
    media_fetcher = MediaFetcher()
    prompts_file = episode_dir / "prompts_payload.json"
    media_fetcher.export_prompt_payload(payload.scenes, prompts_file)
    logger.info(f"💾 Prompts payload saved for AI video tools: {prompts_file}")

    # ----------------------------------------------------
    # STEP 2: CHARISMATIC VOICEOVER NARRATION (Edge-TTS)
    # ----------------------------------------------------
    logger.info("\n[STEP 2/5] Synthesizing voiceover audio & word-level subtitles...")
    audio_path = episode_dir / "narration.mp3"
    subtitles_path = episode_dir / "subtitles.vtt"

    duration = generate_narration_audio(
        text=payload.full_narration,
        output_audio_path=audio_path,
        output_subtitles_path=subtitles_path,
        voice=voice
    )
    logger.info(f"🎙️ Voiceover complete! Duration: {duration:.2f} seconds ({audio_path.name})")

    # Stretch scenes to cover the full narration so generated/animated clips span it
    scene_length = max(config.CLIP_DURATION_SECONDS, duration / len(payload.scenes))
    for s in payload.scenes:
        s.duration_seconds = scene_length

    # ----------------------------------------------------
    # STEP 3: ACQUIRE 8-SECOND SCENE CLIPS
    # ----------------------------------------------------
    logger.info("\n[STEP 3/5] Acquiring stacked 8-second visual clips...")
    clips_dir = episode_dir / "clips"

    # Character portraits keep characters consistent across generated scenes
    portraits = {}
    if not scene_assets and (use_images or use_veo) and payload.characters:
        logger.info(f"🧑 Generating {len(payload.characters)} character portraits for consistency...")
        portraits = media_fetcher.generate_character_portraits(
            payload.characters, payload.style, episode_dir / "characters"
        )

    scene_clips = media_fetcher.acquire_scene_clips(
        payload.scenes,
        clips_dir,
        use_omni=use_omni,
        use_veo=use_veo,
        use_images=use_images,
        scene_assets=scene_assets,
        scene_veo=scene_veo,
        portraits=portraits
    )
    logger.info(f"🎞️ Collected {len(scene_clips)} scene clips ({len(scene_clips) * scene_length:.1f}s visual bank)")

    # ----------------------------------------------------
    # STEP 4: COMPOSING VIDEO & BURNING SUBTITLES
    # ----------------------------------------------------
    logger.info("\n[STEP 4/5] Compositing 9:16 Short, merging audio & burning subtitles...")
    composer = VideoComposer()
    final_video_path = episode_dir / "parable_tales_final.mp4"

    # Total duration matches voiceover narration length
    composer.render_final_short(
        scene_clips=scene_clips,
        audio_path=audio_path,
        subtitles_vtt_path=subtitles_path,
        output_video_path=final_video_path,
        total_duration=duration
    )
    logger.info(f"🎬 Video rendered successfully: {final_video_path}")

    # ----------------------------------------------------
    # STEP 5: YOUTUBE UPLOAD / PUBLISHING
    # ----------------------------------------------------
    upload_result = None
    if upload and not dry_run:
        logger.info("\n[STEP 5/5] Uploading video to YouTube Data API v3...")
        uploader = YouTubeUploader()
        try:
            upload_result = uploader.upload_video(
                video_path=final_video_path,
                title=payload.title,
                description=payload.description,
                tags=payload.tags,
                privacy_status=privacy
            )
        except Exception as e:
            if strict_upload:
                raise
            logger.error(f"❌ Upload failed: {e}. Falling back to dry-run simulation.")
            upload_result = mock_upload_dry_run(final_video_path, payload.title, payload.tags)
    elif dry_run or not upload:
        logger.info("\n[STEP 5/5] Skipping live upload (Dry-run / Local generation mode).")
        upload_result = mock_upload_dry_run(final_video_path, payload.title, payload.tags)

    elapsed = time.time() - start_time
    logger.info("\n" + "=" * 65)
    logger.info("🎉 PIPELINE RUN COMPLETED SUCCESSFULLY!")
    logger.info(f"⏱️ Total Execution Time: {elapsed:.2f} seconds")
    logger.info(f"📹 Final Video Path: {final_video_path}")
    if upload_result:
        logger.info(f"🔗 Video URL: {upload_result.get('url')}")
        logger.info(f"🔒 Privacy Status: {upload_result.get('privacy')}")
    logger.info("=" * 65)

    return {
        "episode_dir": str(episode_dir),
        "video_path": str(final_video_path),
        "payload": payload.model_dump(),
        "upload_result": upload_result
    }


def main():
    parser = argparse.ArgumentParser(
        description="Parable Tales: Autonomous YouTube Video Posting Pipeline"
    )
    parser.add_argument(
        "--topic",
        type=str,
        default="Jonah Running from God (The Most Reluctant Prophet)",
        help="Biblical story or topic for the episode"
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload the rendered video to YouTube upon completion"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run full generation and mock upload without hitting YouTube API"
    )
    parser.add_argument(
        "--use-omni",
        action="store_true",
        help=f"Generate 3D scene clips autonomously using Google Omni Model ({config.VIDEO_MODEL}) via Gemini API"
    )
    parser.add_argument(
        "--use-veo",
        action="store_true",
        help=f"Generate scene clips with Veo ({config.VEO_MODEL}) on the Google Cloud agent platform"
    )
    parser.add_argument(
        "--use-images",
        action="store_true",
        help=f"Generate a still image per scene with Gemini ({config.IMAGE_MODEL}) and animate it into an 8s zoom clip"
    )
    parser.add_argument(
        "--style",
        type=str,
        default=config.DEFAULT_VISUAL_STYLE,
        choices=list(config.VISUAL_STYLES),
        help="Visual style for scene prompts: 3d, realistic or cartoon"
    )
    parser.add_argument(
        "--voice",
        type=str,
        default=config.DEFAULT_VOICE,
        help="Voice model name (e.g. en-US-ChristopherNeural or en-NG-AbeoNeural)"
    )
    parser.add_argument(
        "--privacy",
        type=str,
        default=config.YOUTUBE_DEFAULT_PRIVACY,
        choices=["private", "unlisted", "public"],
        help="Privacy setting on YouTube (default: private)"
    )

    args = parser.parse_args()
    run_pipeline(
        topic=args.topic,
        upload=args.upload,
        dry_run=args.dry_run,
        use_omni=args.use_omni,
        use_veo=args.use_veo,
        use_images=args.use_images,
        style=args.style,
        voice=args.voice,
        privacy=args.privacy
    )


if __name__ == "__main__":
    main()
