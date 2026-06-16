#!/usr/bin/env python3
"""Optional Demucs stem split and lightweight remix before mastering."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Separate a generated mix into stems and lightly remix them.")
    parser.add_argument("--input", default="outputs/lyria_full_song.mp3", help="Input audio")
    parser.add_argument("--spec", default="mix_specs/gate_b28_mix_spec.json", help="Mix spec JSON")
    parser.add_argument("--work-dir", default="outputs/stems", help="Stem working directory")
    parser.add_argument("--output", default="outputs/lyria_full_song_stem_mix.wav", help="Stem remix WAV output")
    return parser.parse_args()


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def load_spec(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def gain_filter(db: float) -> str:
    return f"volume={db}dB"


def main() -> int:
    args = parse_args()
    demucs = shutil.which("demucs")
    if demucs is None:
        print("Demucs is not installed. Install it separately to use --stems mode.")
        return 2

    input_path = Path(args.input)
    work_dir = Path(args.work_dir)
    output_path = Path(args.output)
    spec = load_spec(Path(args.spec))
    stem_spec = spec.get("stem_processing", {})

    if not input_path.exists():
        print(f"Missing input audio: {input_path}")
        return 2

    result = run([demucs, "--two-stems", "vocals", "-o", str(work_dir), str(input_path)])
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        return result.returncode

    stem_root = work_dir / "htdemucs" / input_path.stem
    vocals = stem_root / "vocals.wav"
    no_vocals = stem_root / "no_vocals.wav"
    if not vocals.exists() or not no_vocals.exists():
        print(f"Could not find Demucs stems in {stem_root}")
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    vocals_gain = float(stem_spec.get("vocals_gain_db", 0.0))
    other_gain = float(stem_spec.get("other_gain_db", 0.0))

    # Conservative two-stem remix: keep the accompaniment coherent, adjust vocal balance only.
    filter_complex = (
        f"[0:a]{gain_filter(vocals_gain)}[v];"
        f"[1:a]{gain_filter(other_gain)}[o];"
        "[v][o]amix=inputs=2:normalize=0[out]"
    )
    remix = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(vocals),
            "-i",
            str(no_vocals),
            "-filter_complex",
            filter_complex,
            "-map",
            "[out]",
            str(output_path),
        ]
    )
    if remix.returncode != 0:
        print(remix.stderr)
        return remix.returncode

    print(f"Wrote approximate stem remix to {output_path}")
    print(stem_spec.get("warning", "Stem separation is approximate and may contain artifacts."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
