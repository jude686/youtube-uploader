import config


def make_client(http_options=None):
    """
    Builds a google-genai client for either backend:
    - Gemini Developer API (AI Studio key), the default
    - Google Cloud agent platform / Vertex AI express-mode key, when GEMINI_USE_VERTEX=1
    """
    from google import genai

    return genai.Client(
        api_key=config.GEMINI_API_KEY,
        vertexai=config.GEMINI_USE_VERTEX,
        http_options=http_options,
    )
