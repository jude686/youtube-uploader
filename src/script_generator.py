import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

import config

logger = logging.getLogger("ParableTales.ScriptGenerator")


class ScenePrompt(BaseModel):
    scene_number: int
    duration_seconds: float = 8.0
    narration: str = Field(
        ...,
        description="Narration spoken by the charismatic voiceover for this 8s segment."
    )
    visual_description: str = Field(
        ...,
        description="Raw visual description of the 3D cinematic comic scene."
    )
    final_visual_prompt: str = Field(
        ...,
        description="Prompt payload with injected 3D comic and closed-mouth constraints."
    )
    b_roll_search_keyword: str = Field(
        ...,
        description="Simple search keywords for stock footage fallback."
    )


class VideoPayload(BaseModel):
    title: str
    title_options: List[str]
    book_chapter: str
    description: str
    tags: List[str]
    scenes: List[ScenePrompt]
    full_narration: str
    cta_question: str


def build_system_prompt() -> str:
    return f"""You are the lead viral scriptwriter and creative director for '{config.BRAND_NAME}'.
Channel Brand & Niche: {config.NICHE_DESCRIPTION}.

MISSION:
Create high-retention YouTube Shorts (32 to 48 seconds total) blending scripturally accurate biblical narratives with modern, relatable storytelling, comedic cultural tension (including relatable Nigerian/African comedy elements when fitting), and a profound faith-based life lesson.

AUDIO ARCHITECTURE CONSTRAINTS:
1. The video is driven EXCLUSIVELY by a charismatic voiceover narrator.
2. NO ON-SCREEN LIP-SYNCING. Characters on screen must have their mouths completely closed at all times.

PACING CONSTRAINT:
The video MUST be composed of exactly 4 to 6 stacked scenes.
Each scene MUST correspond to exactly {config.CLIP_DURATION_SECONDS} seconds of visual generation.

NARRATIVE ARC:
1. Scene 1 - Modern, Relatable Hook: Start with high emotional stakes, dramatic tension, or modern situational comedy (e.g., dodging calls, sibling rivalry, pride before a fall).
2. Scenes 2-4 - The Biblical Event: The scripturally accurate biblical encounter, packed with vivid 3D visual drama.
3. Scene 5 - Practical Life Lesson: Bridge the ancient story to our daily walk with God.
4. Scene 6 - Comment-Driving Call to Action (CTA): An open-ended question that forces viewers to debate or comment in the replies.

METADATA REQUIREMENTS:
1. Title Format Archetypes: Provide options following:
   - Format A: '[Modern Hook/Curiosity] (Bible Character/Story)' (e.g., 'When You Try To Ghost God (Jonah's Story) #Shorts')
   - Format B: 'The [Adjective] [Event] in the Bible' (e.g., 'The Most Savage Disobedience in the Bible #Shorts')
2. Tags: Must include: {json.dumps(config.BASE_TAGS)} plus the specific '[Book Chapter]' (e.g., 'Jonah 1').
3. Visual Prompt Injection: Every scene's `final_visual_prompt` MUST end with:
   '{config.VISUAL_PROMPT_INJECTION}'

OUTPUT FORMAT:
Respond with pure JSON conforming to this schema:
{{
  "title": "Selected Primary Title (under 95 chars, includes #Shorts)",
  "title_options": ["Option A", "Option B"],
  "book_chapter": "Specific Book & Chapter reference (e.g. Jonah 1-2)",
  "description": "Engaging description with emojis, brief summary, scripture reference, and hashtags",
  "tags": ["Bible animation", "3D Bible stories", ...],
  "cta_question": "Open-ended question for the comments section",
  "scenes": [
    {{
      "scene_number": 1,
      "duration_seconds": 8.0,
      "narration": "Narration text for this 8-second beat",
      "visual_description": "Vivid visual description of the characters, environment, lighting",
      "final_visual_prompt": "Visual description + ', ' + '{config.VISUAL_PROMPT_INJECTION}'",
      "b_roll_search_keyword": "search terms for fallback b-roll (e.g. ancient storm ocean)"
    }}
  ]
}}
"""


def generate_fallback_script(topic: str) -> VideoPayload:
    """Provides a scripturally accurate, pre-built Parable Tales script when offline or without API key."""
    injected_suffix = config.VISUAL_PROMPT_INJECTION
    return VideoPayload(
        title="When You Try To Ghost God (Jonah & The Whale) #Shorts",
        title_options=[
            "When You Try To Ghost God (Jonah & The Whale) #Shorts",
            "The Most Expensive Uber Ride in the Bible (Jonah) #Shorts"
        ],
        book_chapter="Jonah 1-2",
        description=(
            "Ever tried running away from a job God clearly gave you? Jonah thought he could take a cruise ship to Tarshish, "
            "but God sent a submarine with teeth! Watch how disobedience turned into a 3-day prayer revival inside a giant fish.\n\n"
            "📖 Scripture: Jonah 1-2\n"
            "#ParableTales #BibleStories #ChristianComedy #FaithLessons #Shorts"
        ),
        tags=config.BASE_TAGS + ["Jonah 1-2", "Jonah and the Whale", "Bible Humor"],
        cta_question="If God gave you a difficult assignment today, would you run like Jonah or obey? Be honest in the comments!",
        full_narration=(
            "You know that feeling when your mom calls your full government name and you pretend your phone lost network? "
            "That was Jonah when God said, 'Go to Nineveh.' Instead of booking a ticket to Nineveh, "
            "Jonah packed his bags and paid for a one-way cruise in the complete opposite direction! "
            "Next thing he knew, a violent storm rocked the ship, and the sailors threw him overboard like excess luggage. "
            "God sent a VIP underwater taxi—a giant sea monster that swallowed Jonah whole. "
            "Three days in fish belly acid gave him instant clarity! When God gives you a purpose, you can't run away. "
            "Would you have taken that ship, or obeyed on day one? Tell me below!"
        ),
        scenes=[
            ScenePrompt(
                scene_number=1,
                duration_seconds=8.0,
                narration="You know that feeling when your mom calls your full government name and you pretend your phone lost network? That was Jonah when God said, 'Go to Nineveh.'",
                visual_description="A young Middle Eastern prophet in ancient robes nervously holding travel luggage, tiptoeing away from glowing heavenly light in the clouds",
                final_visual_prompt=f"A young Middle Eastern prophet in ancient robes nervously holding travel luggage, tiptoeing away from glowing heavenly light in the clouds, {injected_suffix}",
                b_roll_search_keyword="ancient port boat dock"
            ),
            ScenePrompt(
                scene_number=2,
                duration_seconds=8.0,
                narration="Instead of booking a ticket to Nineveh, Jonah packed his bags and paid for a one-way luxury cruise in the complete opposite direction!",
                visual_description="A wooden ancient merchant ship sailing toward a sunny horizon away from the coast, dramatic ocean camera angle",
                final_visual_prompt=f"A wooden ancient merchant ship sailing toward a sunny horizon away from the coast, dramatic ocean camera angle, {injected_suffix}",
                b_roll_search_keyword="ancient wooden sailing ship storm"
            ),
            ScenePrompt(
                scene_number=3,
                duration_seconds=8.0,
                narration="Next thing he knew, a violent storm rocked the ship, and the panicked sailors threw him overboard like excess luggage!",
                visual_description="Massive stormy waves crashing over the wooden deck, terrified sailors tossing a man overboard into dark raging waters",
                final_visual_prompt=f"Massive stormy waves crashing over the wooden deck, terrified sailors tossing a man overboard into dark raging waters, {injected_suffix}",
                b_roll_search_keyword="ocean storm waves dark sea"
            ),
            ScenePrompt(
                scene_number=4,
                duration_seconds=8.0,
                narration="God sent a VIP underwater taxi—a colossal sea monster that opened its jaws and swallowed Jonah in one gulp.",
                visual_description="Deep underwater bioluminescent abyss, a colossal mythical whale creature opening massive jaws toward a sinking figure",
                final_visual_prompt=f"Deep underwater bioluminescent abyss, a colossal mythical whale creature opening massive jaws toward a sinking figure, {injected_suffix}",
                b_roll_search_keyword="underwater deep sea whale"
            ),
            ScenePrompt(
                scene_number=5,
                duration_seconds=8.0,
                narration="Three days in fish belly acid gave Jonah instant clarity! When God gives you an assignment, your excuses will never outrun His grace.",
                visual_description="The interior of a surreal glowing cavernous creature belly, Jonah kneeling in deep prayer, glowing spiritual warmth",
                final_visual_prompt=f"The interior of a surreal glowing cavernous creature belly, Jonah kneeling in deep prayer, glowing spiritual warmth, {injected_suffix}",
                b_roll_search_keyword="cave kneeling prayer spiritual light"
            ),
            ScenePrompt(
                scene_number=6,
                duration_seconds=8.0,
                narration="Would you have boarded that ship to Tarshish, or obeyed on day one? Drop your honest answer in the comments!",
                visual_description="Jonah standing victorious on a sunny Nineveh shoreline looking toward the vibrant ancient city, dramatic sunset lens flare",
                final_visual_prompt=f"Jonah standing victorious on a sunny Nineveh shoreline looking toward the vibrant ancient city, dramatic sunset lens flare, {injected_suffix}",
                b_roll_search_keyword="ancient city desert sunset"
            ),
        ]
    )


def generate_script_with_gemini(topic: str, num_scenes: Optional[int] = None) -> VideoPayload:
    """
    Calls Gemini Flash to generate a Parable Tales video script and prompt payload.
    num_scenes forces an exact scene count (e.g. to match user-uploaded scene media).
    """
    api_key = config.GEMINI_API_KEY
    if not api_key:
        logger.warning("GEMINI_API_KEY not found in environment. Using rich Parable Tales fallback.")
        return generate_fallback_script(topic)

    scene_rule = (
        f"Exactly {num_scenes} scenes (this overrides the 4 to 6 rule; compress or expand the narrative arc to fit)"
        if num_scenes else "Exactly 4 to 6 scenes"
    )
    user_prompt = f"""Generate a Parable Tales episode for the topic/story: '{topic}'.
Remember:
- Pacing: {scene_rule}, each strictly {config.CLIP_DURATION_SECONDS} seconds long.
- Visual injection: Append '{config.VISUAL_PROMPT_INJECTION}' to all scene prompts.
- Mouths must be closed, no character lip-syncing!
- Return strictly valid JSON conforming to the schema."""

    # Try modern google-genai SDK first
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        # Target the recommended gemini-3.8-flash with fallback to gemini-flash-latest
        target_model = "gemini-3.8-flash"
        try:
            response = client.models.generate_content(
                model=target_model,
                contents=[build_system_prompt(), user_prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
        except Exception:
            target_model = "gemini-flash-latest"
            response = client.models.generate_content(
                model=target_model,
                contents=[build_system_prompt(), user_prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
        content_text = response.text
    except Exception as e:
        logger.error(f"Failed to generate script via Gemini API: {e}. Falling back to default.")
        return generate_fallback_script(topic)

    try:
        data = json.loads(content_text)
        
        # Verify prompt injection and formatting
        scenes: List[ScenePrompt] = []
        for s in data.get("scenes", []):
            raw_prompt = s.get("final_visual_prompt", s.get("visual_description", ""))
            if config.VISUAL_PROMPT_INJECTION not in raw_prompt:
                final_prompt = f"{raw_prompt.rstrip(', ')}, {config.VISUAL_PROMPT_INJECTION}"
            else:
                final_prompt = raw_prompt

            scenes.append(
                ScenePrompt(
                    scene_number=s.get("scene_number", len(scenes) + 1),
                    duration_seconds=config.CLIP_DURATION_SECONDS,
                    narration=s.get("narration", ""),
                    visual_description=s.get("visual_description", ""),
                    final_visual_prompt=final_prompt,
                    b_roll_search_keyword=s.get("b_roll_search_keyword", "ancient bible story")
                )
            )

        full_narration = " ".join([sc.narration for sc in scenes])
        
        # Ensure default tags are present
        tags = data.get("tags", [])
        for base_tag in config.BASE_TAGS:
            if base_tag not in tags:
                tags.append(base_tag)

        return VideoPayload(
            title=data.get("title", f"The Wildest Story in {data.get('book_chapter', 'The Bible')} #Shorts"),
            title_options=data.get("title_options", [data.get("title", "")]),
            book_chapter=data.get("book_chapter", "The Bible"),
            description=data.get("description", ""),
            tags=tags,
            scenes=scenes,
            full_narration=full_narration,
            cta_question=data.get("cta_question", "What would you do in this situation? Let us know in the comments!")
        )
    except Exception as parse_err:
        logger.error(f"Error parsing Gemini response JSON: {parse_err}. Raw text:\n{content_text}")
        return generate_fallback_script(topic)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    payload = generate_script_with_gemini("Jonah Running from God")
    print(f"Title: {payload.title}")
    print(f"Book/Chapter: {payload.book_chapter}")
    print(f"Total Scenes: {len(payload.scenes)}")
    for scene in payload.scenes:
        print(f"\n[Scene {scene.scene_number}] ({scene.duration_seconds}s)")
        print(f"Voiceover: {scene.narration}")
        print(f"Prompt: {scene.final_visual_prompt}")
