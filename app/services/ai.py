import json
from loguru import logger

from app.core.config import settings

_KEYWORD_MAP = [
    (["fire", "smoke", "burn", "flame", "explosion", "blaze", "inferno", "chemical", "hazmat"], "fire"),
    (["hurt", "injur", "blood", "medi", "pain", "collap", "heart", "unconscious", "casualty",
      "infarction", "poison", "gas", "exposure", "hospital", "ambulance"], "medical"),
    (["crash", "accident", "smash", "collision", "wreck"], "accident"),
    (["theft", "steal", "robbery", "assault", "crime", "loot", "weapon", "shooting", "attack"], "police"),
]


def keyword_classify(description: str) -> list[dict]:
    """Return all matching incident types from keywords — never just one."""
    desc = description.lower()
    found = []
    seen = set()
    for keywords, incident_type in _KEYWORD_MAP:
        if any(k in desc for k in keywords) and incident_type not in seen:
            found.append({"type": incident_type, "severity": 7, "description": description})
            seen.add(incident_type)
    if not found:
        found.append({"type": "police", "severity": 5, "description": description})
    return found


def ai_classify_multi(description: str) -> list[dict]:
    """
    Classify an incident using Groq Llama 3.1.
    Returns a LIST of incidents — one per identified emergency type.
    Falls back to keyword logic if AI unavailable.
    """
    if not settings.groq_api_key:
        logger.warning("GROQ_API_KEY not set — using keyword fallback")
        return keyword_classify(description)

    try:
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI Emergency Dispatcher. Analyze the situation report and identify "
                        "ALL distinct emergency types present. A complex incident may require multiple "
                        "response units.\n\n"
                        "Return ONLY a JSON array where each element has:\n"
                        "  'type': one of 'fire', 'medical', 'police', 'accident'\n"
                        "  'severity': integer 1-10\n"
                        "  'description': concise summary specific to this emergency type\n\n"
                        "Example for a complex incident:\n"
                        '[{"type":"fire","severity":9,"description":"Chemical factory fire with structural collapse"},'
                        '{"type":"medical","severity":8,"description":"Multiple casualties - toxic gas exposure"},'
                        '{"type":"police","severity":6,"description":"Opportunistic theft at scene"}]\n\n'
                        "No markdown. Return ONLY the JSON array."
                    ),
                },
                {"role": "user", "content": description},
            ],
            temperature=0,
            max_tokens=300,
        )
        content = completion.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        incidents = json.loads(content)

        # Validate structure
        result = []
        seen = set()
        for item in incidents:
            t = str(item.get("type", "police")).lower()
            if t not in seen and t in ("fire", "medical", "police", "accident"):
                result.append({
                    "type": t,
                    "severity": int(item.get("severity", 7)),
                    "description": f"{item.get('description', description)} (Severity: {item.get('severity', 7)})",
                })
                seen.add(t)

        if result:
            logger.info("AI identified {n} incident type(s): {types}", n=len(result), types=[r["type"] for r in result])
            return result

    except Exception as exc:
        logger.warning("Groq AI failed ({e}) — falling back to keywords", e=exc)

    return keyword_classify(description)
