import asyncio
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any
import edge_tts

import config


class VoiceEngine:
    def __init__(self, voice: str = config.DEFAULT_VOICE):
        self.voice = voice

    async def generate_speech(
        self,
        text: str,
        output_audio_path: Path,
        output_subtitles_path: Path
    ) -> float:
        """
        Synthesizes speech from text using edge-tts.
        Outputs an MP3 file and a WebVTT/SRT subtitle file.
        Returns the duration of the audio in seconds.
        """
        output_audio_path.parent.mkdir(parents=True, exist_ok=True)
        output_subtitles_path.parent.mkdir(parents=True, exist_ok=True)

        communicate = edge_tts.Communicate(text, self.voice)
        submaker = edge_tts.SubMaker()

        with open(output_audio_path, "wb") as audio_file:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_file.write(chunk["data"])
                elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                    submaker.feed(chunk)

        # Write out SRT/VTT subtitles
        with open(output_subtitles_path, "w", encoding="utf-8") as sub_file:
            sub_file.write(submaker.get_srt())

        # Determine audio duration via moviepy or mutagen
        duration = self._get_audio_duration(output_audio_path)
        return duration

    def _get_audio_duration(self, audio_path: Path) -> float:
        """Calculates audio duration in seconds using moviepy or file size."""
        try:
            from moviepy.editor import AudioFileClip
            clip = AudioFileClip(str(audio_path))
            dur = clip.duration
            clip.close()
            return float(dur)
        except Exception:
            pass

        try:
            size = os.path.getsize(audio_path)
            # edge-tts default is ~128 kbps (16000 bytes per second)
            return max(5.0, size / 16000.0)
        except Exception:
            return 30.0

    @staticmethod
    def parse_vtt_subtitles(vtt_path: Path) -> List[Dict[str, Any]]:
        """Parses WebVTT subtitles into structured cues (start_seconds, end_seconds, text)."""
        if not vtt_path.exists():
            return []

        cues = []
        with open(vtt_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Pattern matching WebVTT and SRT timestamp lines (supports both '.' and ',')
        time_pattern = re.compile(
            r"(\d{2}:\d{2}:\d{2}[,\.]\d{3}|\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3}|\d{2}:\d{2}[,\.]\d{3})"
        )

        blocks = content.replace("\r\n", "\n").split("\n\n")
        for block in blocks:
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            for i, line in enumerate(lines):
                match = time_pattern.search(line)
                if match:
                    start_str, end_str = match.groups()
                    start_sec = VoiceEngine._timestamp_to_seconds(start_str)
                    end_sec = VoiceEngine._timestamp_to_seconds(end_str)
                    text = " ".join(lines[i + 1:])
                    if text:
                        cues.append({
                            "start": start_sec,
                            "end": end_sec,
                            "text": text
                        })
                    break

        return cues

    @staticmethod
    def _timestamp_to_seconds(time_str: str) -> float:
        clean_str = time_str.replace(",", ".")
        parts = clean_str.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        return float(clean_str)


def generate_narration_audio(
    text: str,
    output_audio_path: Path,
    output_subtitles_path: Path,
    voice: str = config.DEFAULT_VOICE
) -> float:
    """Synchronous convenience wrapper for voice generation."""
    engine = VoiceEngine(voice=voice)
    return asyncio.run(
        engine.generate_speech(text, output_audio_path, output_subtitles_path)
    )


if __name__ == "__main__":
    test_text = "Welcome to Parable Tales. What happens when you try to run away from God?"
    out_audio = config.OUTPUT_DIR / "test_voice.mp3"
    out_subs = config.OUTPUT_DIR / "test_voice.vtt"
    dur = generate_narration_audio(test_text, out_audio, out_subs)
    print(f"Generated test voice ({dur:.2f}s) at {out_audio}")
