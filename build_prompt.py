#!/usr/bin/env python3
"""Build a safe Google Lyria prompt from Essentia analysis plus style profile."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


SAFETY_CLAUSE = "Avoid copying any existing melody, lyric, hook, artist voice, or arrangement signature."
DEFAULT_STYLE_PROFILE = "style_profile.json"
STYLE_TEMPLATE = {
    "reference_title": "28.mp3",
    "genre": "replace with accurate genre, e.g. synth-pop, trap, mandopop ballad",
    "era_or_scene": "replace with production era or scene",
    "mood": "replace with emotional tone",
    "instrumentation": ["replace", "with", "actual", "instruments"],
    "target_bpm": 88,
    "target_key": "F minor",
    "meter": "4/4",
    "chord_progression": "Fm9 - Ebmaj7 - Dbmaj7 - C7",
    "groove": "replace with drum pattern / rhythmic feel",
    "vocal_style": "replace with vocal delivery, or 'instrumental' if no vocals",
    "arrangement": "replace with section arc and density changes",
    "section_focus": "replace with the exact section to generate for a 30-second test",
    "production_texture": "replace with mix, reverb, distortion, brightness, space",
    "language": "replace with lyric language, e.g. Traditional Chinese Mandarin",
    "lyric_direction": "replace with lyric handling, e.g. do not translate, do not use pinyin",
    "avoid": [
        "do not copy melody",
        "do not copy lyrics",
        "do not imitate a real artist voice",
    ],
}
PLACEHOLDER_MARKERS = ("replace with", "replace")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a music DNA prompt from Essentia JSON and style profile.")
    parser.add_argument(
        "--analysis",
        default="outputs/reference_essentia.json",
        help="Essentia analysis JSON path",
    )
    parser.add_argument(
        "--output",
        default="outputs/generated_prompt.txt",
        help="Prompt output path",
    )
    parser.add_argument(
        "--style-profile",
        default=DEFAULT_STYLE_PROFILE,
        help="Human/AI style profile JSON path",
    )
    parser.add_argument(
        "--write-style-template",
        action="store_true",
        help="Write a starter style profile template and exit",
    )
    parser.add_argument(
        "--title",
        default="the reference song",
        help="Human label for the reference song",
    )
    return parser.parse_args()


def get_nested(data: dict[str, Any], *paths: str) -> Any:
    for path in paths:
        if path in data:
            return data[path]
        cur: Any = data
        ok = True
        for part in path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        if ok:
            return cur
    return None


def number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    if isinstance(value, list) and value:
        return number(value[0])
    return None


def label_tempo(bpm: float | None) -> str:
    if bpm is None:
        return "a moderate, steady tempo"
    if bpm < 75:
        return f"a slow ballad tempo around {bpm:.0f} BPM"
    if bpm < 105:
        return f"a mid-tempo groove around {bpm:.0f} BPM"
    if bpm < 135:
        return f"an upbeat tempo around {bpm:.0f} BPM"
    return f"a high-energy fast tempo around {bpm:.0f} BPM"


def label_energy(rms: float | None, dynamic_complexity: float | None) -> str:
    if rms is None and dynamic_complexity is None:
        return "a controlled energy arc that builds gradually"
    if dynamic_complexity is not None and dynamic_complexity > 4:
        return "a wide dynamic range with a noticeable emotional build"
    if rms is not None and rms > 0.12:
        return "a strong, forward energy profile"
    return "a restrained energy profile with room for a late-section lift"


def label_brightness(centroid: float | None) -> str:
    if centroid is None:
        return "balanced, polished studio timbre"
    if centroid < 1600:
        return "warm, rounded timbre with a low-mid focus"
    if centroid < 2800:
        return "balanced studio timbre with clear vocal/instrument presence"
    return "bright, crisp timbre with prominent upper-frequency detail"


def label_key(key: Any, scale: Any) -> str:
    if isinstance(key, str) and key:
        if isinstance(scale, str) and scale:
            return f"{key} {scale}"
        return key
    return "an accessible tonal center"


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def required_text(profile: dict[str, Any], key: str) -> str:
    value = profile.get(key)
    if isinstance(value, str) and value.strip():
        text = value.strip()
        if text.lower() in PLACEHOLDER_MARKERS or text.lower().startswith("replace with"):
            raise ValueError(f"style profile field still contains placeholder text: {key}")
        return text
    raise ValueError(f"style profile is missing required text field: {key}")


def required_list(profile: dict[str, Any], key: str) -> list[str]:
    values = as_list(profile.get(key))
    values = [
        item
        for item in values
        if item.lower() not in PLACEHOLDER_MARKERS and not item.lower().startswith("replace with")
    ]
    if values:
        return values
    raise ValueError(f"style profile is missing required list field: {key}")


def optional_text(profile: dict[str, Any], key: str) -> str | None:
    value = profile.get(key)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.lower() in PLACEHOLDER_MARKERS or text.lower().startswith("replace with"):
        return None
    return text


def optional_number(profile: dict[str, Any], key: str) -> float | None:
    value = profile.get(key)
    parsed = number(value)
    return parsed


def load_style_profile(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing style profile: {path}\n"
            f"Create one manually or run: build_prompt.py --write-style-template --style-profile {path}"
        )
    profile = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(profile, dict):
        raise ValueError("style profile must be a JSON object")
    return profile


def write_style_template(path: Path) -> None:
    path.write_text(json.dumps(STYLE_TEMPLATE, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    style_profile_path = Path(args.style_profile)
    if args.write_style_template:
        write_style_template(style_profile_path)
        print(f"Wrote starter style profile to {style_profile_path}")
        return 0

    analysis_path = Path(args.analysis)
    output_path = Path(args.output)
    data = json.loads(analysis_path.read_text(encoding="utf-8"))
    try:
        style_profile = load_style_profile(style_profile_path)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    extracted_bpm = number(get_nested(data, "rhythm.bpm", "lowlevel.bpm"))
    extracted_key = get_nested(data, "tonal.key_edma.key", "tonal.key_krumhansl.key", "tonal.key_temperley.key")
    extracted_scale = get_nested(
        data,
        "tonal.key_edma.scale",
        "tonal.key_krumhansl.scale",
        "tonal.key_temperley.scale",
    )
    centroid = number(get_nested(data, "lowlevel.spectral_centroid.mean"))
    rms = number(get_nested(data, "lowlevel.rms.mean"))
    dynamic_complexity = number(get_nested(data, "lowlevel.dynamic_complexity"))
    danceability = number(get_nested(data, "rhythm.danceability"))

    danceability_phrase = "with a natural song pulse"
    if danceability is not None:
        if danceability >= 1.2:
            danceability_phrase = "with a clear rhythmic pulse"
        else:
            danceability_phrase = "with a more lyrical than dance-driven pulse"

    try:
        reference_title = style_profile.get("reference_title") or args.title
        genre = required_text(style_profile, "genre")
        era_or_scene = required_text(style_profile, "era_or_scene")
        mood = required_text(style_profile, "mood")
        instrumentation = ", ".join(required_list(style_profile, "instrumentation"))
        bpm = optional_number(style_profile, "target_bpm") or extracted_bpm
        key_label = optional_text(style_profile, "target_key") or label_key(extracted_key, extracted_scale)
        meter = optional_text(style_profile, "meter") or "4/4"
        chord_progression = optional_text(style_profile, "chord_progression")
        groove = required_text(style_profile, "groove")
        vocal_style = required_text(style_profile, "vocal_style")
        arrangement = required_text(style_profile, "arrangement")
        section_focus = optional_text(style_profile, "section_focus")
        production_texture = required_text(style_profile, "production_texture")
        language = optional_text(style_profile, "language")
        lyric_direction = optional_text(style_profile, "lyric_direction")
        avoid = "; ".join(as_list(style_profile.get("avoid")))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    chord_sentence = f"Use this broad harmonic color: {chord_progression}. " if chord_progression else ""
    section_sentence = f"For this 30-second test, focus on: {section_focus}. " if section_focus else ""
    language_sentence = f"Language and lyric handling: {language}. {lyric_direction}. " if language or lyric_direction else ""

    prompt = (
        "Create a 30-second original song clip inspired only by broad musical traits from "
        f"{reference_title}. The broad style profile is {genre}, connected to {era_or_scene}. "
        f"Use {label_tempo(bpm)} in {meter}. "
        f"Center the harmony around {key_label} while keeping the chord motion original. "
        f"{chord_sentence}"
        f"Use {label_brightness(centroid)} and {label_energy(rms, dynamic_complexity)} {danceability_phrase}. "
        f"Instrumentation should be based on the style profile: {instrumentation}. "
        f"Groove and rhythm feel: {groove}. Vocal or lead delivery: {vocal_style}. "
        f"Arrangement arc: {arrangement}. {section_sentence}"
        f"Production texture: {production_texture}. {language_sentence}"
        f"Mood and emotional target: {mood}. "
        "All melody, lyrics, and hooks must be newly composed. "
        f"Additional avoid notes: {avoid}. "
        f"{SAFETY_CLAUSE}"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(prompt + "\n", encoding="utf-8")
    print(f"Wrote generation prompt to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
