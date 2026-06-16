#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x ".venv/bin/python" ]]; then
    PYTHON_BIN=".venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

INPUT_PATH="${1:-outputs/lyria_full_song.mp3}"
MODE="${2:-master-only}"
SPEC_PATH="${SPEC_PATH:-mix_specs/gate_b28_mix_spec.json}"
SIDECHAIN_PATH="${SIDECHAIN_PATH:-}"
AUDIO_DUCK_MODE="${AUDIO_DUCK_MODE:-spectral}"

if [[ ! -f "$INPUT_PATH" ]]; then
  echo "Missing input audio: $INPUT_PATH" >&2
  exit 2
fi

if [[ "$MODE" == "--stems" || "$MODE" == "stems" ]]; then
  "$PYTHON_BIN" separate_and_mix_stems.py \
    --input "$INPUT_PATH" \
    --spec "$SPEC_PATH" \
    --output outputs/lyria_full_song_stem_mix.wav
  INPUT_PATH="outputs/lyria_full_song_stem_mix.wav"
fi

if [[ "$MODE" == "--audio-ducking" || "$MODE" == "audio-ducking" ]]; then
  DUCK_ARGS=(
    audio_sidechain_duck.py
    --target "$INPUT_PATH"
    --spec "$SPEC_PATH"
    --mode "$AUDIO_DUCK_MODE"
    --output outputs/lyria_full_song_ducked.wav
    --report outputs/ducking_report.json
  )
  if [[ -n "$SIDECHAIN_PATH" ]]; then
    if [[ ! -f "$SIDECHAIN_PATH" ]]; then
      echo "Missing sidechain audio: $SIDECHAIN_PATH" >&2
      exit 2
    fi
    DUCK_ARGS+=(--sidechain "$SIDECHAIN_PATH")
  fi
  "$PYTHON_BIN" "${DUCK_ARGS[@]}"
  INPUT_PATH="outputs/lyria_full_song_ducked.wav"
fi

"$PYTHON_BIN" postprocess_master.py \
  --input "$INPUT_PATH" \
  --spec "$SPEC_PATH" \
  --wav-output outputs/lyria_full_song_mastered.wav \
  --mp3-output outputs/lyria_full_song_mastered.mp3 \
  --report outputs/mastering_report.json

echo "Post-mix pipeline complete:"
echo "  outputs/lyria_full_song_mastered.wav"
echo "  outputs/lyria_full_song_mastered.mp3"
echo "  outputs/mastering_report.json"
if [[ "$MODE" == "--audio-ducking" || "$MODE" == "audio-ducking" ]]; then
  echo "  outputs/ducking_report.json"
fi
