#!/usr/bin/env python3
"""Pure-audio sidechain and spectral ducking helper.

This intentionally avoids MIDI. It derives trigger events from an audio
sidechain, then applies gain reduction to either a target stem or a full mix.
With clean drum/kick and bass stems the result is materially better; with only
a mixed MP3 it is an approximation.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_SAMPLE_RATE = 44100


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply no-MIDI audio sidechain ducking.")
    parser.add_argument("--target", required=True, help="Audio to duck, usually bass/808 stem or full mix")
    parser.add_argument("--sidechain", help="Audio trigger, usually kick/drum stem. Defaults to --target.")
    parser.add_argument("--spec", default="mix_specs/gate_b28_mix_spec.json", help="Mix spec JSON")
    parser.add_argument("--output", default="outputs/lyria_full_song_ducked.wav", help="Ducked WAV output")
    parser.add_argument("--report", default="outputs/ducking_report.json", help="Ducking report output")
    parser.add_argument(
        "--mode",
        choices=("envelope", "spectral"),
        default="spectral",
        help="Envelope ducks the whole target; spectral ducks selected low-frequency bins.",
    )
    parser.add_argument("--duck-db", type=float, default=None, help="Maximum duck depth in dB")
    parser.add_argument("--min-spacing-sec", type=float, default=None, help="Minimum time between kick events")
    parser.add_argument("--fallback-grid", action="store_true", help="Use tempo grid if too few audio events are detected")
    return parser.parse_args()


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def load_spec(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def decode_audio(path: Path, sample_rate: int = DEFAULT_SAMPLE_RATE) -> tuple[np.ndarray, int]:
    if not path.exists():
        raise FileNotFoundError(f"Missing audio: {path}")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = Path(tmp.name)
    result = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(path),
            "-ar",
            str(sample_rate),
            "-ac",
            "2",
            "-f",
            "wav",
            str(wav_path),
        ]
    )
    if result.returncode != 0:
        wav_path.unlink(missing_ok=True)
        raise RuntimeError(result.stderr)
    try:
        with wave.open(str(wav_path), "rb") as reader:
            channels = reader.getnchannels()
            rate = reader.getframerate()
            frames = reader.readframes(reader.getnframes())
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        audio = audio.reshape(-1, channels)
        return audio, rate
    finally:
        wav_path.unlink(missing_ok=True)


def write_wav(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(audio, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(pcm.shape[1] if pcm.ndim == 2 else 1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(pcm.tobytes())


def frame_signal(signal: np.ndarray, frame_size: int, hop: int) -> np.ndarray:
    if len(signal) < frame_size:
        padded = np.pad(signal, (0, frame_size - len(signal)))
        return padded.reshape(1, frame_size)
    frame_count = 1 + (len(signal) - frame_size) // hop
    shape = (frame_count, frame_size)
    strides = (signal.strides[0] * hop, signal.strides[0])
    return np.lib.stride_tricks.as_strided(signal, shape=shape, strides=strides)


def moving_average(values: np.ndarray, window: int) -> np.ndarray:
    if window <= 1:
        return values
    kernel = np.ones(window, dtype=np.float32) / float(window)
    return np.convolve(values, kernel, mode="same")


def detect_kick_events(
    sidechain: np.ndarray,
    sample_rate: int,
    spec: dict[str, Any],
    min_spacing_sec: float,
    fallback_grid: bool,
) -> tuple[list[float], dict[str, Any]]:
    mono = sidechain.mean(axis=1) if sidechain.ndim == 2 else sidechain
    frame_size = 2048
    hop = 512
    frames = frame_signal(mono, frame_size, hop)
    window = np.hanning(frame_size).astype(np.float32)
    spectrum = np.abs(np.fft.rfft(frames * window, axis=1))
    freqs = np.fft.rfftfreq(frame_size, 1.0 / sample_rate)

    band = (freqs >= 45.0) & (freqs <= 120.0)
    if not np.any(band):
        return [], {"reason": "no_low_frequency_bins"}

    energy = np.sqrt(np.mean(np.square(spectrum[:, band]), axis=1))
    energy = moving_average(energy, 3)
    if float(np.max(energy)) <= 1e-8:
        return [], {"reason": "no_low_frequency_energy"}

    normalized = energy / (float(np.percentile(energy, 95)) + 1e-8)
    onset = np.maximum(0.0, np.diff(normalized, prepend=normalized[0]))
    score = normalized * 0.75 + onset * 1.25
    threshold = max(0.45, float(np.percentile(score, 88)))

    min_spacing_frames = max(1, int(min_spacing_sec * sample_rate / hop))
    candidates = np.where(score >= threshold)[0]
    selected: list[int] = []
    for idx in candidates:
        if selected and idx - selected[-1] < min_spacing_frames:
            if score[idx] > score[selected[-1]]:
                selected[-1] = int(idx)
            continue
        selected.append(int(idx))

    events = [round((idx * hop + frame_size * 0.5) / sample_rate, 4) for idx in selected]
    used_fallback = False
    if len(events) < 4 and fallback_grid:
        tempo = float(spec.get("tempo_bpm", 88))
        duration = len(mono) / sample_rate
        beat = 60.0 / tempo
        events = [round(t, 4) for t in np.arange(0.0, duration, beat)]
        used_fallback = True

    diagnostics = {
        "frame_size": frame_size,
        "hop": hop,
        "band_hz": [45, 120],
        "threshold": round(threshold, 6),
        "raw_candidates": int(len(candidates)),
        "events": len(events),
        "used_fallback_grid": used_fallback,
    }
    return events, diagnostics


def envelope_for_events(
    sample_count: int,
    sample_rate: int,
    events: list[float],
    duck_db: float,
    attack_sec: float,
    hold_sec: float,
    release_sec: float,
) -> np.ndarray:
    envelope = np.ones(sample_count, dtype=np.float32)
    duck_gain = float(10 ** (duck_db / 20.0))
    attack = max(1, int(attack_sec * sample_rate))
    hold = max(1, int(hold_sec * sample_rate))
    release = max(1, int(release_sec * sample_rate))

    for event in events:
        center = int(event * sample_rate)
        start = max(0, center - attack)
        hold_end = min(sample_count, center + hold)
        end = min(sample_count, hold_end + release)
        if start >= sample_count:
            continue
        if center > start:
            ramp_down = np.linspace(1.0, duck_gain, center - start, endpoint=False, dtype=np.float32)
            envelope[start:center] = np.minimum(envelope[start:center], ramp_down)
        envelope[center:hold_end] = np.minimum(envelope[center:hold_end], duck_gain)
        if end > hold_end:
            ramp_up = np.linspace(duck_gain, 1.0, end - hold_end, endpoint=False, dtype=np.float32)
            envelope[hold_end:end] = np.minimum(envelope[hold_end:end], ramp_up)
    return envelope


def apply_envelope_duck(target: np.ndarray, sample_rate: int, events: list[float], duck_db: float) -> np.ndarray:
    env = envelope_for_events(
        sample_count=len(target),
        sample_rate=sample_rate,
        events=events,
        duck_db=duck_db,
        attack_sec=0.006,
        hold_sec=0.035,
        release_sec=0.18,
    )
    return target * env[:, None]


def spectral_duck_channel(channel: np.ndarray, sample_rate: int, events: list[float], duck_db: float) -> np.ndarray:
    frame_size = 2048
    hop = 512
    pad = frame_size
    padded = np.pad(channel, (pad, pad))
    frame_count = 1 + math.ceil((len(padded) - frame_size) / hop)
    needed = (frame_count - 1) * hop + frame_size
    padded = np.pad(padded, (0, max(0, needed - len(padded))))

    output = np.zeros_like(padded, dtype=np.float32)
    norm = np.zeros_like(padded, dtype=np.float32)
    window = np.hanning(frame_size).astype(np.float32)
    freqs = np.fft.rfftfreq(frame_size, 1.0 / sample_rate)
    low_band = (freqs >= 45.0) & (freqs <= 190.0)
    duck_gain = float(10 ** (duck_db / 20.0))

    event_array = np.array(events, dtype=np.float32)
    for frame_idx in range(frame_count):
        start = frame_idx * hop
        center_sec = (start + frame_size * 0.5 - pad) / sample_rate
        frame = padded[start : start + frame_size] * window
        spectrum = np.fft.rfft(frame)
        if len(event_array) and np.min(np.abs(event_array - center_sec)) <= 0.16:
            weights = np.ones_like(freqs, dtype=np.float32)
            # Strongest attenuation near the kick fundamental, lighter above it.
            low_weights = np.interp(freqs[low_band], [45.0, 80.0, 190.0], [0.82, 1.0, 0.35])
            weights[low_band] = 1.0 - low_weights * (1.0 - duck_gain)
            spectrum *= weights
        rendered = np.fft.irfft(spectrum, n=frame_size).astype(np.float32) * window
        output[start : start + frame_size] += rendered
        norm[start : start + frame_size] += window * window

    valid = norm > 1e-8
    output[valid] /= norm[valid]
    return output[pad : pad + len(channel)]


def apply_spectral_duck(target: np.ndarray, sample_rate: int, events: list[float], duck_db: float) -> np.ndarray:
    channels = []
    for channel_idx in range(target.shape[1]):
        channels.append(spectral_duck_channel(target[:, channel_idx], sample_rate, events, duck_db))
    return np.stack(channels, axis=1)


def main() -> int:
    args = parse_args()
    target_path = Path(args.target)
    sidechain_path = Path(args.sidechain) if args.sidechain else target_path
    spec = load_spec(Path(args.spec))
    audio_spec = spec.get("audio_sidechain", {})

    duck_db = float(args.duck_db if args.duck_db is not None else audio_spec.get("duck_db", -4.0))
    min_spacing = float(args.min_spacing_sec if args.min_spacing_sec is not None else audio_spec.get("min_spacing_sec", 0.28))

    target, sample_rate = decode_audio(target_path)
    sidechain, sidechain_rate = decode_audio(sidechain_path, sample_rate)
    if sidechain_rate != sample_rate:
        raise RuntimeError(f"Unexpected sample-rate mismatch: {sample_rate} vs {sidechain_rate}")

    events, detection = detect_kick_events(
        sidechain=sidechain,
        sample_rate=sample_rate,
        spec=spec,
        min_spacing_sec=min_spacing,
        fallback_grid=args.fallback_grid,
    )
    if not events:
        print("No usable kick/low-frequency events detected. No ducked file was written.")
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(
            json.dumps({"ok": False, "detection": detection}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return 2

    if args.mode == "envelope":
        ducked = apply_envelope_duck(target, sample_rate, events, duck_db)
    else:
        ducked = apply_spectral_duck(target, sample_rate, events, duck_db)

    peak = float(np.max(np.abs(ducked))) if ducked.size else 0.0
    if peak > 0.999:
        ducked = ducked / peak * 0.999

    output_path = Path(args.output)
    write_wav(output_path, ducked, sample_rate)

    report = {
        "ok": True,
        "mode": args.mode,
        "target": str(target_path),
        "sidechain": str(sidechain_path),
        "output": str(output_path),
        "duck_db": duck_db,
        "event_count": len(events),
        "first_events_sec": events[:20],
        "detection": detection,
        "limitations": [
            "No MIDI was used.",
            "Commercial Trackspacer/Soothe2 behavior is approximated, not duplicated.",
            "If target and sidechain are the same mixed MP3, this is full-mix low-band ducking, not clean kick-versus-808 mixing.",
        ],
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote ducked audio to {output_path}")
    print(f"Wrote ducking report to {report_path}")
    print(f"Detected {len(events)} audio trigger events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
