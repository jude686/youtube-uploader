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
        description="Raw visual description of the scene (no art style; that is appended)."
    )
    final_visual_prompt: str = Field(
        ...,
        description="Prompt payload with injected visual style and closed-mouth constraints."
    )
    b_roll_search_keyword: str = Field(
        ...,
        description="Simple search keywords for stock footage fallback."
    )
    characters: List[str] = Field(
        default_factory=list,
        description="Names of recurring characters (from VideoPayload.characters) visible in this scene."
    )


class Character(BaseModel):
    name: str
    description: str = Field(
        ...,
        description="Fixed visual description reused verbatim in every scene so the character stays consistent."
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
    characters: List[Character] = Field(default_factory=list)
    style: str = config.DEFAULT_VISUAL_STYLE


def build_system_prompt(style: str = config.DEFAULT_VISUAL_STYLE) -> str:
    injection = config.visual_injection(style)
    style_label = config.VISUAL_STYLES.get(style, config.VISUAL_STYLES["3d"])["label"]
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
2. Scenes 2-4 - The Biblical Event: The scripturally accurate biblical encounter, packed with vivid visual drama.
3. Scene 5 - Practical Life Lesson: Bridge the ancient story to our daily walk with God.
4. Scene 6 - Comment-Driving Call to Action (CTA): An open-ended question that forces viewers to debate or comment in the replies.

METADATA REQUIREMENTS:
1. Title Format Archetypes: Provide options following:
   - Format A: '[Modern Hook/Curiosity] (Bible Character/Story)' (e.g., 'When You Try To Ghost God (Jonah's Story) #Shorts')
   - Format B: 'The [Adjective] [Event] in the Bible' (e.g., 'The Most Savage Disobedience in the Bible #Shorts')
2. Tags: Must include: {json.dumps(config.BASE_TAGS)} plus the specific '[Book Chapter]' (e.g., 'Jonah 1').
3. Visual Style: This episode is in {style_label} style. Write every `visual_description` so it suits that style
   (subjects, setting, lighting, camera angle), but don't name an art style in it; the style is appended automatically.
4. Visual Prompt Injection: Every scene's `final_visual_prompt` MUST end with:
   '{injection}'

CHARACTER CONSISTENCY:
1. List every recurring on-screen character (people and notable creatures, max 4) in `characters`, each with a
   fixed, specific visual `description`: age, build, skin tone, face, hair, facial hair, and exact clothing with
   colors and accessories. No art-style words, no poses, no actions. This exact description is reused in every scene.
2. In each scene, refer to characters by NAME only (e.g. "David grips his sling"); do not re-describe their
   appearance, clothing or age, and never contradict the character sheet.
3. List the names of the characters visible in each scene in that scene's `characters` array (empty if none).

OUTPUT FORMAT:
Respond with pure JSON conforming to this schema:
{{
  "title": "Selected Primary Title (under 95 chars, includes #Shorts)",
  "title_options": ["Option A", "Option B"],
  "book_chapter": "Specific Book & Chapter reference (e.g. Jonah 1-2)",
  "description": "Engaging description with emojis, brief summary, scripture reference, and hashtags",
  "tags": ["Bible animation", "3D Bible stories", ...],
  "cta_question": "Open-ended question for the comments section",
  "characters": [
    {{"name": "David", "description": "16-year-old shepherd boy, slim build, olive skin, curly shoulder-length black hair, ..."}}
  ],
  "scenes": [
    {{
      "scene_number": 1,
      "duration_seconds": 8.0,
      "narration": "Narration text for this 8-second beat",
      "visual_description": "Vivid description of the action, environment, lighting and camera, naming characters",
      "characters": ["David"],
      "final_visual_prompt": "Visual description + ', ' + '{injection}'",
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


class ScriptGenerationError(RuntimeError):
    """Raised when no Gemini model could write the script (and fallback is disabled)."""


def _parse_payload(content_text: str, style: str = config.DEFAULT_VISUAL_STYLE) -> VideoPayload:
    data = json.loads(content_text)
    injection = config.visual_injection(style)

    characters = [
        Character(name=c["name"].strip(), description=c["description"].strip().rstrip("."))
        for c in data.get("characters", []) if c.get("name") and c.get("description")
    ]
    by_name = {c.name.lower(): c for c in characters}

    # Build each final prompt as description + character sheet entries + chosen style, rather
    # than trusting the model's final_visual_prompt (it sometimes drops or mixes the style suffix)
    scenes: List[ScenePrompt] = []
    for s in data.get("scenes", []):
        description = (s.get("visual_description") or s.get("final_visual_prompt", "")).strip().rstrip(",.")
        scene_chars = [by_name[n.strip().lower()].name for n in s.get("characters", []) if n.strip().lower() in by_name]
        final_prompt = f"{description}. {character_block(scene_chars, characters)}{injection}"

        scenes.append(
            ScenePrompt(
                scene_number=s.get("scene_number", len(scenes) + 1),
                duration_seconds=config.CLIP_DURATION_SECONDS,
                narration=s.get("narration", ""),
                visual_description=s.get("visual_description", ""),
                final_visual_prompt=final_prompt,
                b_roll_search_keyword=s.get("b_roll_search_keyword", "ancient bible story"),
                characters=scene_chars,
            )
        )
    if not scenes:
        raise ValueError("response contained no scenes")

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
        cta_question=data.get("cta_question", "What would you do in this situation? Let us know in the comments!"),
        characters=characters,
        style=style,
    )


def rebuild_scene_prompts(payload: "VideoPayload") -> None:
    """Re-derives every scene's final prompt, e.g. after a character description is edited."""
    injection = config.visual_injection(payload.style)
    for sc in payload.scenes:
        description = sc.visual_description.strip().rstrip(",.")
        sc.final_visual_prompt = f"{description}. {character_block(sc.characters, payload.characters)}{injection}"


def character_block(names: List[str], characters: List["Character"]) -> str:
    """Verbatim character-sheet text for the characters in a scene (empty if none)."""
    by_name = {c.name: c for c in characters}
    parts = [f"{n}: {by_name[n].description}" for n in names if n in by_name]
    return ("Characters: " + "; ".join(parts) + ". ") if parts else ""


def generate_script_with_gemini(
    topic: str,
    num_scenes: Optional[int] = None,
    allow_fallback: bool = True,
    style: str = config.DEFAULT_VISUAL_STYLE
) -> VideoPayload:
    """
    Calls Gemini Flash to generate a Parable Tales video script and prompt payload.
    num_scenes forces an exact scene count (e.g. to match user-uploaded scene media).
    style is a key of config.VISUAL_STYLES (3d, realistic, cartoon).
    Tries each model in config.SCRIPT_MODELS in turn (free-tier models are often
    rate-limited or overloaded). If all fail: returns the built-in Jonah script when
    allow_fallback is True, otherwise raises ScriptGenerationError.
    """
    def fail(reason: str) -> VideoPayload:
        if not allow_fallback:
            raise ScriptGenerationError(reason)
        logger.warning(f"{reason} Using the built-in Jonah fallback script (topic '{topic}' ignored).")
        return generate_fallback_script(topic)

    api_key = config.GEMINI_API_KEY
    if not api_key:
        return fail("GEMINI_API_KEY is not set.")

    scene_rule = (
        f"Exactly {num_scenes} scenes (this overrides the 4 to 6 rule; compress or expand the narrative arc to fit)"
        if num_scenes else "Exactly 4 to 6 scenes"
    )
    user_prompt = f"""Generate a Parable Tales episode for the topic/story: '{topic}'.
Remember:
- Pacing: {scene_rule}, each strictly {config.CLIP_DURATION_SECONDS} seconds long.
- Visual style: {config.VISUAL_STYLES.get(style, config.VISUAL_STYLES['3d'])['label']}. Append '{config.visual_injection(style)}' to all scene prompts.
- Mouths must be closed, no character lip-syncing!
- Return strictly valid JSON conforming to the schema."""

    from google.genai import types
    from src.genai_client import make_client

    # One attempt per model with a per-call timeout: on 429/503/timeouts it's faster
    # to move to the next model than to let the SDK keep retrying the same one
    client = make_client(
        http_options=types.HttpOptions(
            timeout=config.SCRIPT_TIMEOUT_SECONDS * 1000,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )

    errors = []
    for model in config.SCRIPT_MODELS:
        try:
            logger.info(f"Writing script with {model}...")
            response = client.models.generate_content(
                model=model,
                contents=[build_system_prompt(style), user_prompt],
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            payload = _parse_payload(response.text, style)
            logger.info(f"Script written by {model}")
            return payload
        except Exception as e:
            short = str(e).split(". {")[0][:160]
            logger.warning(f"{model} failed: {short}")
            errors.append(f"{model}: {short}")

    return fail("Every Gemini model failed (" + "; ".join(errors) + ").")


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
