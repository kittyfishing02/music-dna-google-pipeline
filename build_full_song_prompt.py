#!/usr/bin/env python3
"""Build a Lyria 3 Pro prompt for a full song from a brief and lyrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SAFETY_CLAUSE = "Do not imitate any named artist, voice, cadence, flow, beat, melody, lyric, hook, or arrangement signature."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a full-song prompt for Lyria 3 Pro.")
    parser.add_argument("--brief", default="briefs/gate_b28_song_brief.json", help="Song brief JSON path")
    parser.add_argument("--lyrics", default="lyrics/gate_b28_lyrics.md", help="Verbatim lyrics path")
    parser.add_argument("--style-profile", default="style_profile.json", help="Optional style profile JSON path")
    parser.add_argument("--output", default="outputs/full_song_prompt.txt", help="Prompt output path")
    parser.add_argument("--duration", default="2 minutes 45 seconds", help="Target full-song duration")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def bullet_list(values: Any) -> str:
    if not values:
        return "- none"
    if isinstance(values, dict):
        return "\n".join(f"- {key}: {value}" for key, value in values.items())
    if isinstance(values, list):
        return "\n".join(f"- {value}" for value in values)
    return f"- {values}"


def section_list(sections: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for section in sections:
        name = section.get("name", "Section")
        time = section.get("time")
        production = section.get("production", "")
        if time:
            lines.append(f"- {name} ({time}): {production}")
        else:
            lines.append(f"- {name}: {production}")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    brief = load_json(Path(args.brief))
    lyrics = Path(args.lyrics).read_text(encoding="utf-8").strip()
    style_profile_path = Path(args.style_profile)
    style_profile = load_json(style_profile_path) if style_profile_path.exists() else {}

    tempo = brief.get("tempo", {})
    sound_palette = brief.get("sound_palette", {})
    vocal_production = brief.get("vocal_production", {})
    lyrics_policy = brief.get("lyrics_policy", {})

    prompt = f"""Create a full-length Spotify-ready demo song titled "{brief.get("title", "Untitled")}" with subtitle "{brief.get("subtitle", "")}".

Target duration: {args.duration}.
Language: {lyrics_policy.get("language", "Traditional Chinese Mandarin")}.
Use the provided lyrics verbatim where possible. Do not translate to English. Do not use pinyin. Do not summarize, replace, or rewrite the lyrics unless timing absolutely forces a small omission. Preserve the section order and preserve the hook wording.

Core positioning:
{brief.get("core_positioning", "")}

Core meaning:
{brief.get("core_meaning", "")}

Broad style:
- Genre: {style_profile.get("genre", "Taiwanese Mandarin narrative hip-hop")}
- Scene: {style_profile.get("era_or_scene", "late-night Taipei office-worker headphone music")}
- Mood: {brief.get("core_meaning", "")}

Tempo, key, and harmony:
- BPM: {tempo.get("bpm", 88)} BPM. Do not exceed {tempo.get("max_bpm", 95)} BPM.
- Feel: {tempo.get("feel", "walking pace, thoughtful")}
- Key: {brief.get("key", "F minor")}
- Chord progression: {brief.get("chord_progression", "Fm9 - Ebmaj7 - Dbmaj7 - C7")}
- Main instrument: {brief.get("main_instrument", "Rhodes Electric Piano")}

Sound palette:
{bullet_list(sound_palette)}

Vocal production:
{bullet_list(vocal_production)}

Arrangement:
{section_list(brief.get("sections", []))}

Do not make this:
{bullet_list(brief.get("not_this", []))}

Safety and originality:
{SAFETY_CLAUSE}
The song may share broad musical traits with the brief, but all melody, flow, arrangement execution, and sound design must be original.

Provided lyrics:
```text
{lyrics}
```
"""

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(prompt, encoding="utf-8")
    print(f"Wrote full-song prompt to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
