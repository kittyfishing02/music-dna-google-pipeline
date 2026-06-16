#!/usr/bin/env python3
"""Post-process a Lyria output into a measured streaming-demo master."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Master a generated song to streaming-demo targets.")
    parser.add_argument("--input", default="outputs/lyria_full_song.mp3", help="Input Lyria audio")
    parser.add_argument("--spec", default="mix_specs/gate_b28_mix_spec.json", help="Mix spec JSON")
    parser.add_argument("--wav-output", default="outputs/lyria_full_song_mastered.wav", help="Mastered WAV output")
    parser.add_argument("--mp3-output", default="outputs/lyria_full_song_mastered.mp3", help="Mastered MP3 output")
    parser.add_argument("--report", default="outputs/mastering_report.json", help="Validation report path")
    return parser.parse_args()


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def load_spec(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def loudnorm_pass(input_path: Path, target_lufs: float, true_peak: float) -> dict[str, Any]:
    result = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(input_path),
            "-af",
            f"loudnorm=I={target_lufs}:TP={true_peak}:LRA=11:print_format=json",
            "-f",
            "null",
            "-",
        ]
    )
    text = result.stderr
    start = text.rfind("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise RuntimeError(f"Could not parse ffmpeg loudnorm measurement:\n{text[-2000:]}")
    return json.loads(text[start : end + 1])


def normalize_to_wav(input_path: Path, output_path: Path, spec: dict[str, Any]) -> None:
    target_lufs = float(spec.get("target_lufs", -14.0))
    true_peak = float(spec.get("mastering", {}).get("encoding_true_peak_db", spec.get("true_peak_db", -1.0)))
    measured = loudnorm_pass(input_path, target_lufs, true_peak)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    filter_value = (
        f"loudnorm=I={target_lufs}:TP={true_peak}:LRA=11:"
        f"measured_I={measured['input_i']}:"
        f"measured_TP={measured['input_tp']}:"
        f"measured_LRA={measured['input_lra']}:"
        f"measured_thresh={measured['input_thresh']}:"
        f"offset={measured['target_offset']}:"
        "linear=true:print_format=summary"
    )
    result = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-af",
            filter_value,
            "-ar",
            str(spec.get("mastering", {}).get("wav_sample_rate", 44100)),
            "-ac",
            str(spec.get("mastering", {}).get("wav_channels", 2)),
            str(output_path),
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr)


def wav_to_mp3(wav_path: Path, mp3_path: Path, spec: dict[str, Any]) -> None:
    bitrate = spec.get("mastering", {}).get("codec_mp3_bitrate", "320k")
    result = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(wav_path),
            "-codec:a",
            "libmp3lame",
            "-b:a",
            str(bitrate),
            str(mp3_path),
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr)


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    spec_path = Path(args.spec)
    wav_output = Path(args.wav_output)
    mp3_output = Path(args.mp3_output)

    if not input_path.exists():
        print(f"Missing input audio: {input_path}")
        return 2
    spec = load_spec(spec_path)
    normalize_to_wav(input_path, wav_output, spec)
    wav_to_mp3(wav_output, mp3_output, spec)

    validate = run(
        [
            ".venv/bin/python" if Path(".venv/bin/python").exists() else "python3",
            "validate_master.py",
            "--input",
            str(mp3_output),
            "--spec",
            str(spec_path),
            "--output",
            args.report,
        ]
    )
    print(validate.stdout)
    if validate.returncode != 0:
        print(validate.stderr)
        return validate.returncode
    print(f"Wrote mastered WAV to {wav_output}")
    print(f"Wrote mastered MP3 to {mp3_output}")
    print(f"Wrote mastering report to {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
