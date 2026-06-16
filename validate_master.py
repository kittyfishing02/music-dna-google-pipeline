#!/usr/bin/env python3
"""Validate loudness, peak, duration, stereo correlation, and silence gaps."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a mastered audio file.")
    parser.add_argument("--input", default="outputs/lyria_full_song_mastered.mp3", help="Audio file to validate")
    parser.add_argument("--spec", default="mix_specs/gate_b28_mix_spec.json", help="Mix spec JSON path")
    parser.add_argument("--output", default="outputs/mastering_report.json", help="Report JSON path")
    return parser.parse_args()


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def load_spec(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ffprobe_duration(path: Path) -> float | None:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    if result.returncode != 0:
        return None
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def loudnorm_measure(path: Path) -> dict[str, Any]:
    result = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            "loudnorm=I=-14:TP=-1:LRA=11:print_format=json",
            "-f",
            "null",
            "-",
        ]
    )
    text = result.stderr
    start = text.rfind("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {"error": "Could not parse loudnorm output", "stderr_tail": text[-2000:]}
    return json.loads(text[start : end + 1])


def silence_detect(path: Path) -> list[dict[str, float]]:
    result = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            "silencedetect=noise=-45dB:d=0.25",
            "-f",
            "null",
            "-",
        ]
    )
    silences: list[dict[str, float]] = []
    pending_start: float | None = None
    for line in result.stderr.splitlines():
        start_match = re.search(r"silence_start: ([0-9.]+)", line)
        if start_match:
            pending_start = float(start_match.group(1))
            continue
        end_match = re.search(r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)", line)
        if end_match and pending_start is not None:
            silences.append(
                {
                    "start": pending_start,
                    "end": float(end_match.group(1)),
                    "duration": float(end_match.group(2)),
                }
            )
            pending_start = None
    return silences


def stereo_correlation(path: Path) -> float | None:
    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = Path(tmpdir) / "analysis.wav"
        result = run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(path),
                "-ac",
                "2",
                "-ar",
                "44100",
                "-sample_fmt",
                "s16",
                str(wav_path),
            ]
        )
        if result.returncode != 0:
            return None
        with wave.open(str(wav_path), "rb") as wav:
            frames = wav.readframes(wav.getnframes())
            data = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
        if data.size < 4:
            return None
        stereo = data.reshape((-1, 2))
        left = stereo[:, 0]
        right = stereo[:, 1]
        if np.std(left) == 0 or np.std(right) == 0:
            return None
        corr = float(np.corrcoef(left, right)[0, 1])
        if math.isnan(corr):
            return None
        return corr


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    spec = load_spec(Path(args.spec))
    loudness = loudnorm_measure(input_path)
    measured_lufs = as_float(loudness.get("input_i"))
    measured_tp = as_float(loudness.get("input_tp"))
    target_lufs = float(spec.get("target_lufs", -14.0))
    max_tp = float(spec.get("true_peak_db", -1.0))

    report = {
        "input": str(input_path),
        "duration_sec": ffprobe_duration(input_path),
        "loudnorm": loudness,
        "integrated_lufs": measured_lufs,
        "true_peak_dbtp": measured_tp,
        "target_lufs": target_lufs,
        "target_true_peak_dbtp": max_tp,
        "lufs_delta": measured_lufs - target_lufs if measured_lufs is not None else None,
        "passes_lufs_tolerance": abs(measured_lufs - target_lufs) <= 1.0 if measured_lufs is not None else False,
        "passes_true_peak": measured_tp <= max_tp if measured_tp is not None else False,
        "stereo_correlation": stereo_correlation(input_path),
        "silence_gaps": silence_detect(input_path),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
