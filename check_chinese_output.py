#!/usr/bin/env python3
"""Check Chinese output and rough lyric adherence."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Chinese ratio and lyric overlap.")
    parser.add_argument("--expected", default="lyrics/gate_b28_lyrics.md", help="Expected lyrics path")
    parser.add_argument("--actual", default="outputs/lyria_full_song_response.txt", help="Lyria response text path")
    parser.add_argument("--output", default="outputs/lyric_adherence_report.txt", help="Report output path")
    return parser.parse_args()


def chinese_chars(text: str) -> list[str]:
    return [char for char in text if "\u4e00" <= char <= "\u9fff"]


def latin_chars(text: str) -> list[str]:
    return [char for char in text if ("A" <= char <= "Z") or ("a" <= char <= "z")]


def lyric_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("Left channel") or line.startswith("Right channel"):
            continue
        line = re.sub(r"^\[(?:\d+(?:\.\d+)?)?:[^\]]*\]\s*", "", line)
        if line.startswith("[") or re.fullmatch(r"\[\[[A-Z]\d+\]\]", line):
            continue
        if chinese_chars(line):
            lines.append(line)
    return lines


def normalize(text: str) -> str:
    return "".join(chinese_chars(text))


def main() -> int:
    args = parse_args()
    expected_text = Path(args.expected).read_text(encoding="utf-8")
    actual_text = Path(args.actual).read_text(encoding="utf-8")

    expected_lines = lyric_lines(expected_text)
    actual_lines = lyric_lines(actual_text)
    actual_chars = [char for char in actual_text if not char.isspace()]
    zh = chinese_chars(actual_text)
    latin = latin_chars(actual_text)

    expected_normalized = normalize("\n".join(expected_lines))
    actual_normalized = normalize("\n".join(actual_lines))
    matched_lines = [line for line in expected_lines if normalize(line) and normalize(line) in actual_normalized]
    matched_chars = sum(len(normalize(line)) for line in matched_lines)
    expected_chars = len(expected_normalized)
    overlap = matched_chars / expected_chars if expected_chars else 0.0
    chinese_ratio = len(zh) / len(actual_chars) if actual_chars else 0.0

    report = f"""Chinese / lyric adherence report

expected_lines={len(expected_lines)}
actual_lines={len(actual_lines)}
matched_expected_lines={len(matched_lines)}
expected_chinese_chars={expected_chars}
matched_chinese_chars={matched_chars}
line_based_overlap={overlap:.3f}
actual_chinese_chars={len(zh)}
actual_latin_chars={len(latin)}
actual_chinese_ratio={chinese_ratio:.3f}

Matched lines:
{chr(10).join(matched_lines) if matched_lines else "(none)"}
"""

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
