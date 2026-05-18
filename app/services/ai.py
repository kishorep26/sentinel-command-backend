import json
from loguru import logger

from app.core.config import settings

_KEYWORD_MAP = [
    (["fire", "smoke", "burn", "flame", "explosion", "blaze", "inferno"], "fire"),
    (["hurt", "injur", "blood", "medi", "pain", "collap", "heart", "unconscious", "casualty", "infarction"], "medical"),
    (["crash", "accident", "smash", "collision", "wreck"], "accident"),
]


def keyword_classify(description: str) -> str:
    desc = description.lower()
    for keywords, result_type in _KEYWORD_MAP:
        if any(k in desc for k in keywords):
            return result_type
    return "police"


def ai_classify(description: str) -> tuple[str, str]:
    """
    Classify an incident using Groq Llama 3.1.
    Returns (incident_type, enriched_description).
    Falls back to keyword logic if AI unavailable.
    """
    if not settings.groq_api_key:
        logger.warning("GROQ_API_KEY not set — using keyword fallback")
        return keyword_classify(description), description

    try:
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI Dispatcher. Analyze the emergency description. "
                        "Return ONLY a JSON object with keys: "
                        "'type' (one of: fire, medical, police, accident), "
                        "'severity' (1-10 int), "
                        "'risk_analysis' (short string). "
                        "No markdown formatting."
                    ),
                },
                {"role": "user", "content": description},
            ],
            temperature=0,
            max_tokens=100,
        )
        content = completion.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        data = json.loads(content)
        incident_type = data.get("type", "police").lower()
        enriched = f"{data.get('risk_analysis', description)} (Severity: {data.get('severity')})"
        logger.info("AI classified as {t}", t=incident_type)
        return incident_type, enriched
    except Exception as exc:
        logger.warning("Groq AI failed ({e}) — falling back to keywords", e=exc)
        return keyword_classify(description), description
