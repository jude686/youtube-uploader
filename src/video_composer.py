import logging
import os
import subprocess
from pathlib import Path
from typing import List, Optional
import imageio_ffmpeg

import config
from src.voice_engine import VoiceEngine

logger = logging.getLogger("ParableTales.VideoComposer")


class VideoComposer:
    def __init__(self):
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    def generate_styled_ass_subtitles(
        self,
        vtt_path: Path,
        ass_path: Path,
        font_size: int = 56,
        brand_label: str = config.BRAND_NAME
    ):
        """
        Converts WebVTT into Advanced SubStation Alpha (.ass) format with
        optimal YouTube Shorts safe zone placement (MarginV=560) and 2-4 centered lines.
        Automatically breaks long sentences into punchy 2-3 second chunks so text
        never overflows screen width.
        """
        import textwrap
        raw_cues = VoiceEngine.parse_vtt_subtitles(vtt_path)

        # Smart cue chunking: break long cues into 2-3s chunks of 6-9 words each
        processed_cues = []
        max_words_per_cue = 8
        max_chars_per_line = 22

        for cue in raw_cues:
            words = cue["text"].replace("\n", " ").strip().split()
            duration = cue["end"] - cue["start"]
            if len(words) > max_words_per_cue and duration > 2.5:
                num_chunks = max(2, (len(words) + max_words_per_cue - 1) // max_words_per_cue)
                words_per_chunk = len(words) // num_chunks
                time_per_chunk = duration / num_chunks

                for i in range(num_chunks):
                    s_idx = i * words_per_chunk
                    e_idx = (i + 1) * words_per_chunk if i < num_chunks - 1 else len(words)
                    chunk_words = words[s_idx:e_idx]
                    chunk_text = " ".join(chunk_words).upper()
                    lines = textwrap.wrap(chunk_text, width=max_chars_per_line)
                    formatted_text = r"\N".join(lines)

                    processed_cues.append({
                        "start": cue["start"] + (i * time_per_chunk),
                        "end": cue["start"] + ((i + 1) * time_per_chunk),
                        "text": formatted_text
                    })
            else:
                clean_text = " ".join(words).upper()
                lines = textwrap.wrap(clean_text, width=max_chars_per_line)
                formatted_text = r"\N".join(lines)
                processed_cues.append({
                    "start": cue["start"],
                    "end": cue["end"],
                    "text": formatted_text
                })

        header = f"""[Script Info]
Title: {brand_label} Shorts
ScriptType: v4.00+
PlayResX: {config.VIDEO_WIDTH}
PlayResY: {config.VIDEO_HEIGHT}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Impact,{font_size},&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,4,2,2,80,120,560,1
Style: BrandHeader,Arial,36,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,3,1,8,40,40,140,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        lines = [header]

        def sec_to_ass_time(sec: float) -> str:
            h = int(sec // 3600)
            m = int((sec % 3600) // 60)
            s = sec % 60
            return f"{h:01d}:{m:02d}:{s:05.2f}"

        # Add brand watermarking at top of screen throughout video
        max_duration = processed_cues[-1]["end"] + 1.0 if processed_cues else 60.0
        lines.append(
            f"Dialogue: 0,0:00:00.00,{sec_to_ass_time(max_duration)},BrandHeader,,0,0,0,,★ {brand_label.upper()} ★\n"
        )

        for cue in processed_cues:
            start_str = sec_to_ass_time(cue["start"])
            end_str = sec_to_ass_time(cue["end"])
            lines.append(
                f"Dialogue: 1,{start_str},{end_str},Default,,0,0,0,,{cue['text']}\n"
            )

        ass_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ass_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        logger.info(f"Generated styled .ass subtitles at {ass_path} ({len(processed_cues)} dynamic chunks)")

    def render_final_short(
        self,
        scene_clips: List[Path],
        audio_path: Path,
        subtitles_vtt_path: Path,
        output_video_path: Path,
        total_duration: float
    ) -> Path:
        """
        Composites stacked 8-second clips, stitches them with narration audio,
        burns styled animated subtitles, and outputs a 1080x1920 MP4 file.
        """
        output_video_path.parent.mkdir(parents=True, exist_ok=True)
        ass_subtitles = output_video_path.parent / "subtitles.ass"
        concat_txt = output_video_path.parent / "concat_list.txt"

        # 1. Build .ass subtitles
        self.generate_styled_ass_subtitles(subtitles_vtt_path, ass_subtitles)

        # 2. Normalize and prepare scene clips list for FFmpeg concatenation.
        # Scenes stretch to cover the whole narration (never shorter than the 8s pacing),
        # so the voiceover isn't cut off when it runs longer than scenes x 8s.
        clip_duration = max(config.CLIP_DURATION_SECONDS, total_duration / max(len(scene_clips), 1))
        normalized_clips = []
        for i, clip in enumerate(scene_clips):
            norm_clip = output_video_path.parent / f"norm_clip_{i:02d}.mp4"
            # Normalize each clip to 1080x1920 @ 30fps
            scale_filter = (
                f"scale={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT},setsar=1,fps={config.VIDEO_FPS}"
            )
            cmd_norm = [
                self.ffmpeg_exe, "-y",
                "-stream_loop", "-1",  # loop clips shorter than the scene length
                "-i", str(clip),
                "-t", f"{clip_duration:.3f}",
                "-vf", scale_filter,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-an",
                str(norm_clip)
            ]
            subprocess.run(cmd_norm, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            normalized_clips.append(norm_clip)

        # 3. Create concat list
        with open(concat_txt, "w", encoding="utf-8") as f:
            for nc in normalized_clips:
                clean_path = str(nc.resolve()).replace("\\", "/")
                f.write(f"file '{clean_path}'\n")

        # 4. Concatenate and merge with voiceover and subtitles
        # Windows-safe path escaping for the subtitles filter
        ass_escaped = str(ass_subtitles.resolve()).replace("\\", "/").replace(":", "\\:")
        subtitle_filter = f"subtitles='{ass_escaped}'"

        cmd_final = [
            self.ffmpeg_exe, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_txt),
            "-i", str(audio_path),
            "-vf", subtitle_filter,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "20",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-t", str(total_duration),
            "-movflags", "+faststart",
            str(output_video_path)
        ]

        logger.info(f"Rendering final Parable Tales Short to {output_video_path}...")
        result = subprocess.run(cmd_final, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            logger.warning(f"Subtitles filter encounter issue: {result.stderr}. Retrying without subtitle filter...")
            # Fallback without subtitles burn if subtitle filter has fontconfig issue on Windows
            cmd_fallback = [
                self.ffmpeg_exe, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_txt),
                "-i", str(audio_path),
                "-c:v", "libx264",
                "-c:a", "aac",
                "-shortest",
                "-t", str(total_duration),
                str(output_video_path)
            ]
            subprocess.run(cmd_fallback, check=True)

        logger.info(f"Video rendering complete: {output_video_path}")
        return output_video_path
