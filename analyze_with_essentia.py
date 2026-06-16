#!/usr/bin/env python3
"""Analyze a reference track with Essentia.

Preferred path: call the Essentia command-line extractor if available.
Fallback path: use the Python Essentia MusicExtractor binding.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze a music file with Essentia.")
    parser.add_argument("--input", default="input/reference.mp3", help="Reference audio path")
    parser.add_argument(
        "--output",
        default="outputs/reference_essentia.json",
        help="Output JSON path",
    )
    return parser.parse_args()


def run_cli_extractor(input_path: Path, output_path: Path) -> bool:
    extractor = shutil.which("essentia_streaming_extractor_music")
    if extractor is None:
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [extractor, str(input_path), str(output_path)]
    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            "Essentia CLI extractor failed:\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return True


def pool_to_plain(value: Any) -> Any:
    """Convert Essentia/numpy values into JSON-serializable Python values."""
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, dict):
        return {str(k): pool_to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [pool_to_plain(v) for v in value]
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def run_python_extractor(input_path: Path, output_path: Path) -> None:
    try:
        import essentia.standard as es  # type: ignore
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "Essentia is not available. Install the CLI extractor with Homebrew "
            "or install Python bindings with `pip install essentia`."
        ) from exc

    extractor = es.MusicExtractor()
    extracted = extractor(str(input_path))
    pool = extracted[0] if isinstance(extracted, tuple) else extracted
    data = {name: pool_to_plain(pool[name]) for name in pool.descriptorNames()}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Missing input audio: {input_path}", file=sys.stderr)
        print("Put a reference track at input/reference.mp3 or pass --input.", file=sys.stderr)
        return 2

    try:
        if not run_cli_extractor(input_path, output_path):
            run_python_extractor(input_path, output_path)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Wrote Essentia analysis to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
