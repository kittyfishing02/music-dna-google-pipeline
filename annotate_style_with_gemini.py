#!/usr/bin/env python3
"""Draft a style_profile.json from a reference audio file with Gemini.

The generated profile is a starting point. Review and edit it before generation.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import traceback
from pathlib import Path
from typing import Any


STYLE_PROMPT = """Listen to this reference track and produce a JSON style profile for lawful music style study.

Do not identify or imitate a specific artist. Do not transcribe lyrics. Do not copy melody or hook.
Describe only broad style traits that can guide an original new composition.

Return only JSON with these keys:
{
  "reference_title": "string",
  "genre": "string",
  "era_or_scene": "string",
  "mood": "string",
  "instrumentation": ["string"],
  "groove": "string",
  "vocal_style": "string",
  "arrangement": "string",
  "production_texture": "string",
  "avoid": ["string"]
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Draft a style profile from audio using Gemini.")
    parser.add_argument("--input", default="input/reference.mp3", help="Reference audio path")
    parser.add_argument("--output", default="style_profile.json", help="Style profile JSON output path")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Gemini model for style annotation")
    parser.add_argument("--error-output", default="outputs/style_annotation_error.txt", help="Error output path")
    return parser.parse_args()


def extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Gemini response did not contain a JSON object")
    return data


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    error_output = Path(args.error_output)

    try:
        from dotenv import load_dotenv
        from google import genai
        from google.genai import types

        load_dotenv()

        if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
            print("Missing GEMINI_API_KEY or GOOGLE_API_KEY environment variable.", file=sys.stderr)
            return 2
        if not input_path.exists():
            print(f"Missing input audio: {input_path}", file=sys.stderr)
            return 2

        mime_type = mimetypes.guess_type(input_path.name)[0] or "audio/mpeg"
        audio_part = types.Part.from_bytes(data=input_path.read_bytes(), mime_type=mime_type)

        client = genai.Client()
        response = client.models.generate_content(
            model=args.model,
            contents=[STYLE_PROMPT, audio_part],
        )

        text = getattr(response, "text", None) or ""
        profile = extract_json(text)
        output_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if error_output.exists():
            error_output.unlink()
        print(f"Wrote drafted style profile to {output_path}")
        print("Review and edit it before running the generation pipeline.")
        return 0
    except Exception as exc:
        error_output.parent.mkdir(parents=True, exist_ok=True)
        error_output.write_text(
            f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}",
            encoding="utf-8",
        )
        print(f"Style annotation failed. Details written to {error_output}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
