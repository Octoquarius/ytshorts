"""Stage 2 (Step 4) — 3 scene prompt generation (Claude).

Generates 3 separate scene descriptions, each 1000–2000 characters, with
camera work and motion, from the Idea + Environment + Sound input. These
prompts are fed to Wavespeed Seedance as text-to-video input.
"""
from __future__ import annotations

import json

import anthropic

import config

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

_SCENES_SCHEMA = {
    "type": "object",
    "properties": {
        "scenes": {
            "type": "array",
            "items": {"type": "string"},
        }
    },
    "required": ["scenes"],
    "additionalProperties": False,
}


def generate_scene_prompts(idea: str, environment: str, sound: str) -> list[str]:
    """Generates 3 scene prompts (each 1000–2000 chars, with motion/camera work)."""
    prompt = (
        "You are a prompt engineer for a text-to-video model (ByteDance Seedance).\n"
        "Create EXACTLY 3 distinct scene prompts for a vertical (9:16) ASMR short.\n\n"
        f"Idea: {idea}\n"
        f"Environment: {environment}\n"
        f"Sound: {sound}\n\n"
        "Requirements for EACH of the 3 scene prompts:\n"
        "- Between 1000 and 2000 characters.\n"
        "- Vivid, highly detailed, cinematic.\n"
        "- Describe explicit camera movement (push-in, slow pan, macro dolly, etc.).\n"
        "- Describe motion/action happening in the scene (the ASMR action).\n"
        "- Keep continuity: the 3 scenes form one coherent ~30s sequence.\n"
        "- No text overlays, no watermarks, no humans speaking.\n"
        'Return JSON: {"scenes": ["...", "...", "..."]} with exactly 3 strings.'
    )

    response = _client.messages.create(
        model=config.CLAUDE_PROMPT_MODEL,
        max_tokens=8000,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": _SCENES_SCHEMA},
        },
        messages=[{"role": "user", "content": prompt}],
    )
    text = next((b.text for b in response.content if b.type == "text"), "")
    data = json.loads(text)
    scenes = data.get("scenes", [])
    if len(scenes) != 3:
        raise RuntimeError(f"Expected 3 scenes, got {len(scenes)}.")
    return scenes


if __name__ == "__main__":
    demo = generate_scene_prompts(
        idea="golden kinetic sand being sliced",
        environment="soft studio light on a matte black table",
        sound="crisp granular slicing and crumbling",
    )
    for i, s in enumerate(demo, 1):
        print(f"--- Scene {i} ({len(s)} chars) ---\n{s}\n")
