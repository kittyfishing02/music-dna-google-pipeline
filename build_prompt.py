#!/usr/bin/env python3
"""Build a safe Google Lyria prompt from Essentia analysis JSON."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SAFETY_CLAUSE = "Avoid copying any existing melody, lyric, hook, artist voice, or arrangement signature."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a music DNA prompt from Essentia JSON.")
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


def main() -> int:
    args = parse_args()
    analysis_path = Path(args.analysis)
    output_path = Path(args.output)
    data = json.loads(analysis_path.read_text(encoding="utf-8"))

    bpm = number(get_nested(data, "rhythm.bpm", "lowlevel.bpm"))
    key = get_nested(data, "tonal.key_edma.key", "tonal.key_krumhansl.key", "tonal.key_temperley.key")
    scale = get_nested(
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

    prompt = (
        "Create a 30-second original song clip inspired only by broad musical traits from "
        f"{args.title}. Use {label_tempo(bpm)} in 4/4 unless another meter is musically necessary. "
        f"Center the harmony around {label_key(key, scale)} with accessible pop/gospel-compatible chord motion. "
        f"Use {label_brightness(centroid)} and {label_energy(rms, dynamic_complexity)} {danceability_phrase}. "
        "Arrange it with a clear intro gesture, an intimate lead-vocal or lead-instrument phrase, "
        "then a wider chorus-like lift with layered backing vocals or choir-like harmony. "
        "Use piano or keys, warm bass, restrained drums, and soft pad or ensemble textures. "
        "The mood should be hopeful, communal, sincere, and emotionally direct. "
        "All melody, lyrics, and hooks must be newly composed. "
        f"{SAFETY_CLAUSE}"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(prompt + "\n", encoding="utf-8")
    print(f"Wrote generation prompt to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
