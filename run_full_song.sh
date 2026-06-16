#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x ".venv/bin/python" ]]; then
    PYTHON_BIN=".venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

if [[ -z "${GEMINI_API_KEY:-}" && -z "${GOOGLE_API_KEY:-}" ]]; then
  echo "Missing GEMINI_API_KEY or GOOGLE_API_KEY." >&2
  echo "Set one in the current shell or .env before running this script." >&2
  exit 2
fi

"$PYTHON_BIN" build_full_song_prompt.py \
  --brief briefs/gate_b28_song_brief.json \
  --lyrics lyrics/gate_b28_lyrics.md \
  --style-profile style_profile.json \
  --output outputs/full_song_prompt.txt

"$PYTHON_BIN" generate_lyria_full_song.py \
  --prompt outputs/full_song_prompt.txt \
  --audio-output outputs/lyria_full_song.mp3 \
  --text-output outputs/lyria_full_song_response.txt \
  --error-output outputs/lyria_full_song_error.txt

"$PYTHON_BIN" check_chinese_output.py \
  --expected lyrics/gate_b28_lyrics.md \
  --actual outputs/lyria_full_song_response.txt \
  --output outputs/lyric_adherence_report.txt

echo "Full-song pipeline complete:"
echo "  outputs/full_song_prompt.txt"
echo "  outputs/lyria_full_song.mp3"
echo "  outputs/lyria_full_song_response.txt"
echo "  outputs/lyric_adherence_report.txt"
