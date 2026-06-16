#!/usr/bin/env python3
"""Generate a full song with Google Lyria 3 Pro from a prompt."""

from __future__ import annotations

import argparse
import base64
import os
import sys
import traceback
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a full song with Lyria 3 Pro.")
    parser.add_argument("--prompt", default="outputs/full_song_prompt.txt", help="Prompt text path")
    parser.add_argument("--audio-output", default="outputs/lyria_full_song.mp3", help="MP3 output path")
    parser.add_argument("--text-output", default="outputs/lyria_full_song_response.txt", help="Response text output path")
    parser.add_argument("--error-output", default="outputs/lyria_full_song_error.txt", help="Error capture path")
    parser.add_argument("--model", default="lyria-3-pro-preview", help="Gemini Lyria model ID")
    return parser.parse_args()


def get_parts(response: object) -> list[object]:
    parts = getattr(response, "parts", None)
    if parts is not None:
        return list(parts)
    candidates = getattr(response, "candidates", None) or []
    if candidates:
        content = getattr(candidates[0], "content", None)
        parts = getattr(content, "parts", None)
        if parts is not None:
            return list(parts)
    return []


def inline_bytes(inline_data: object) -> bytes | None:
    data = getattr(inline_data, "data", None)
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return base64.b64decode(data)
    return None


def main() -> int:
    args = parse_args()
    prompt_path = Path(args.prompt)
    audio_output = Path(args.audio_output)
    text_output = Path(args.text_output)
    error_output = Path(args.error_output)

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
        print("Missing GEMINI_API_KEY or GOOGLE_API_KEY environment variable.", file=sys.stderr)
        return 2
    if not prompt_path.exists():
        print(f"Missing prompt file: {prompt_path}", file=sys.stderr)
        return 2

    try:
        from google import genai

        client = genai.Client()
        response = client.models.generate_content(
            model=args.model,
            contents=prompt_path.read_text(encoding="utf-8"),
        )

        text_parts: list[str] = []
        audio_data: bytes | None = None
        for part in get_parts(response):
            text = getattr(part, "text", None)
            if text:
                text_parts.append(str(text))
            inline_data = getattr(part, "inline_data", None) or getattr(part, "inlineData", None)
            if inline_data is not None:
                maybe_audio = inline_bytes(inline_data)
                if maybe_audio:
                    audio_data = maybe_audio

        text_output.parent.mkdir(parents=True, exist_ok=True)
        text_output.write_text("\n\n".join(text_parts).strip() + "\n", encoding="utf-8")

        if not audio_data:
            raise RuntimeError("Lyria Pro response did not contain audio inline data.")

        audio_output.parent.mkdir(parents=True, exist_ok=True)
        audio_output.write_bytes(audio_data)
        if error_output.exists():
            error_output.unlink()

        print(f"Wrote Lyria full song to {audio_output}")
        print(f"Wrote Lyria response text to {text_output}")
        return 0
    except Exception as exc:
        error_output.parent.mkdir(parents=True, exist_ok=True)
        error_output.write_text(
            f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}",
            encoding="utf-8",
        )
        print(f"Lyria full-song generation failed. Details written to {error_output}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
