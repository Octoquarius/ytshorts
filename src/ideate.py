"""Stage 1 — Idea Generation (Claude).

Two steps:
1. `generate_idea(theme)`  → generates a one-line, viral, < 10-word ASMR
   concept based on the account's theme. Since each account has a different
   theme, the output is unique.
2. `expand_to_plan(idea)`  → expands the idea into a structured production
   JSON (Caption, Idea, Environment, Sound, Status).

The generated idea can be checked against previously used ideas (a dedupe
list) to prevent repeats — see `generate_unique_idea`.
"""
from __future__ import annotations

import json

import anthropic

import config

# Single client; ANTHROPIC_API_KEY is read from the environment.
_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

# Plan JSON schema — guarantees structured output.
_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "Caption": {"type": "string"},   # 1 emoji + 12 hashtags
        "Idea": {"type": "string"},      # (color/style) (object) being (action)
        "Environment": {"type": "string"},  # < 20-word scene description
        "Sound": {"type": "string"},     # < 15-word sound description
        "Status": {"type": "string"},
    },
    "required": ["Caption", "Idea", "Environment", "Sound", "Status"],
    "additionalProperties": False,
}


def generate_idea(theme: str, avoid: list[str] | None = None) -> str:
    """Generates a one-line viral ASMR idea matching the account's theme."""
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
    """Expands the one-line idea into a structured production plan."""
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
    """Dedupe: returns an idea that doesn't collide with used ideas."""
    used_lower = {u.strip().lower() for u in used_ideas}
    idea = ""
    for _ in range(attempts):
        idea = generate_idea(theme, avoid=used_ideas)
        if idea.strip().lower() not in used_lower:
            return idea
    # Still colliding after the last attempt — return what we have (caller logs it).
    return idea


if __name__ == "__main__":
    # Quick manual test: python -m src.ideate
    demo_theme = "kinetic sand cutting and crushing"
    one = generate_idea(demo_theme)
    print("IDEA:", one)
    print("PLAN:", json.dumps(expand_to_plan(one, demo_theme), indent=2))
