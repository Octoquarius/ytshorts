"""Aşama 1 — Fikir Üretimi (Claude).

İki adım:
1. `generate_idea(theme)`  → hesabın temasına göre tek satırlık, viral, < 10 kelime
   bir ASMR konsepti üretir. Her hesabın farklı teması olduğu için çıktı benzersizdir.
2. `expand_to_plan(idea)`  → fikri yapılandırılmış prodüksiyon JSON'una genişletir
   (Caption, Idea, Environment, Sound, Status).

Üretilen fikir, daha önce kullanılmış fikirlere (dedupe listesi) karşı kontrol
edilerek tekrar engellenebilir — bkz. `generate_unique_idea`.
"""
from __future__ import annotations

import json

import anthropic

import config

# Tek istemci; ANTHROPIC_API_KEY ortamdan okunur.
_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

# Plan JSON şeması — yapılandırılmış çıktı garantisi için.
_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "Caption": {"type": "string"},   # 1 emoji + 12 hashtag
        "Idea": {"type": "string"},      # (renk/stil) (nesne) being (aksiyon)
        "Environment": {"type": "string"},  # < 20 kelime sahne tanımı
        "Sound": {"type": "string"},     # < 15 kelime ses tanımı
        "Status": {"type": "string"},
    },
    "required": ["Caption", "Idea", "Environment", "Sound", "Status"],
    "additionalProperties": False,
}


def generate_idea(theme: str, avoid: list[str] | None = None) -> str:
    """Hesabın temasına uygun, tek satırlık viral ASMR fikri üretir."""
    avoid = avoid or []
    avoid_block = ""
    if avoid:
        joined = "\n".join(f"- {a}" for a in avoid[-30:])
        avoid_block = (
            "\n\nDo NOT repeat or closely resemble any of these already-used ideas:\n"
            f"{joined}"
        )

    prompt = (
        f"Theme: {theme}.\n"
        "Give me ONE single-line, viral, extremely simple ASMR short-video concept "
        "for this theme. Fewer than 10 words. No punctuation at the end, no quotes, "
        "no explanation — output only the concept line."
        f"{avoid_block}"
    )

    response = _client.messages.create(
        model=config.CLAUDE_IDEA_MODEL,
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    text = next((b.text for b in response.content if b.type == "text"), "")
    return text.strip().strip('"').strip()


def expand_to_plan(idea: str, theme: str) -> dict:
    """Tek satırlık fikri yapılandırılmış prodüksiyon planına genişletir."""
    prompt = (
        f"ASMR theme: {theme}\n"
        f"ASMR concept: {idea}\n\n"
        "Expand this into a production plan as JSON with exactly these fields:\n"
        '- "Caption": an engaging caption with exactly 1 emoji followed by 12 '
        "relevant hashtags (English).\n"
        '- "Idea": short phrase shaped as "(color/style) (object) being (action)".\n'
        '- "Environment": scene description, fewer than 20 words.\n'
        '- "Sound": the ASMR sound description, fewer than 15 words.\n'
        '- "Status": always the literal string "for production".\n'
        "All text must be in English."
    )

    response = _client.messages.create(
        model=config.CLAUDE_PROMPT_MODEL,
        max_tokens=1024,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": _PLAN_SCHEMA},
        },
        messages=[{"role": "user", "content": prompt}],
    )
    text = next((b.text for b in response.content if b.type == "text"), "")
    return json.loads(text)


def generate_unique_idea(theme: str, used_ideas: list[str], attempts: int = 3) -> str:
    """Dedupe: kullanılmış fikirlerle çakışmayan bir fikir döndürür."""
    used_lower = {u.strip().lower() for u in used_ideas}
    idea = ""
    for _ in range(attempts):
        idea = generate_idea(theme, avoid=used_ideas)
        if idea.strip().lower() not in used_lower:
            return idea
    # Son denemede bile çakışıyorsa elimizdekini döndür (çağıran loglar).
    return idea


if __name__ == "__main__":
    # Hızlı manuel test: python -m src.ideate
    demo_theme = "kinetic sand cutting and crushing"
    one = generate_idea(demo_theme)
    print("IDEA:", one)
    print("PLAN:", json.dumps(expand_to_plan(one, demo_theme), indent=2))
