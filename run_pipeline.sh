#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

INPUT_PATH="${1:-input/reference.mp3}"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

if [[ ! -f "$INPUT_PATH" ]]; then
  echo "Missing input audio: $INPUT_PATH" >&2
  echo "Put a reference track at input/reference.mp3 or pass a file path as the first argument." >&2
  exit 2
fi

if [[ -z "${GEMINI_API_KEY:-}" && -z "${GOOGLE_API_KEY:-}" ]]; then
  echo "Missing GEMINI_API_KEY or GOOGLE_API_KEY." >&2
  echo "Set one in the current shell before running this script." >&2
  exit 2
fi

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x ".venv/bin/python" ]]; then
    PYTHON_BIN=".venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

"$PYTHON_BIN" analyze_with_essentia.py --input "$INPUT_PATH" --output outputs/reference_essentia.json
"$PYTHON_BIN" build_prompt.py --analysis outputs/reference_essentia.json --output outputs/generated_prompt.txt
"$PYTHON_BIN" generate_lyria_clip.py \
  --prompt outputs/generated_prompt.txt \
  --audio-output outputs/lyria_clip.mp3 \
  --text-output outputs/lyria_response.txt \
  --error-output outputs/lyria_error.txt

if [[ ! -s outputs/lyria_clip.mp3 ]]; then
  echo "Generation completed without a non-empty MP3 output." >&2
  exit 1
fi

echo "Pipeline complete:"
echo "  outputs/reference_essentia.json"
echo "  outputs/generated_prompt.txt"
echo "  outputs/lyria_response.txt"
echo "  outputs/lyria_clip.mp3"
