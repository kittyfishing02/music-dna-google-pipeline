#!/usr/bin/env python3
"""Generate a 30-second Google Lyria 3 clip from a prompt."""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a Lyria 3 clip with Gemini API.")
    parser.add_argument("--prompt", default="outputs/generated_prompt.txt", help="Prompt text path")
    parser.add_argument("--audio-output", default="outputs/lyria_clip.mp3", help="MP3 output path")
    parser.add_argument(
        "--text-output",
        default="outputs/lyria_response.txt",
        help="Returned text/structure output path",
    )
    parser.add_argument(
        "--error-output",
        default="outputs/lyria_error.txt",
        help="Error capture path",
    )
    parser.add_argument("--model", default="lyria-3-clip-preview", help="Gemini Lyria model ID")
    return parser.parse_args()


def get_inline_data(part: object) -> object | None:
    if hasattr(part, "inline_data"):
        return getattr(part, "inline_data")
    if hasattr(part, "inlineData"):
        return getattr(part, "inlineData")
    return None


def inline_data_bytes(inline_data: object) -> bytes | None:
    data = getattr(inline_data, "data", None)
    if data is None:
        return None
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        import base64

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
        audio_bytes: bytes | None = None

        parts = getattr(response, "parts", None)
        if parts is None:
            candidates = getattr(response, "candidates", None) or []
            if candidates:
                content = getattr(candidates[0], "content", None)
                parts = getattr(content, "parts", None)

        for part in parts or []:
            text = getattr(part, "text", None)
            if text:
                text_parts.append(str(text))

            inline_data = get_inline_data(part)
            if inline_data is not None:
                maybe_bytes = inline_data_bytes(inline_data)
                if maybe_bytes:
                    audio_bytes = maybe_bytes

        text_output.parent.mkdir(parents=True, exist_ok=True)
        text_output.write_text("\n\n".join(text_parts).strip() + "\n", encoding="utf-8")

        if not audio_bytes:
            raise RuntimeError("Lyria response did not contain audio inline data.")

        audio_output.parent.mkdir(parents=True, exist_ok=True)
        audio_output.write_bytes(audio_bytes)
        if error_output.exists():
            error_output.unlink()

        print(f"Wrote Lyria clip to {audio_output}")
        print(f"Wrote Lyria response text to {text_output}")
        return 0
    except Exception as exc:
        error_output.parent.mkdir(parents=True, exist_ok=True)
        error_output.write_text(
            f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}",
            encoding="utf-8",
        )
        print(f"Lyria generation failed. Details written to {error_output}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
