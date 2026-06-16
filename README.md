# Music DNA Google Pipeline

Analyze a reference song with Essentia, turn the analysis into a safe music-style study prompt, and generate a 30-second clip with Google Lyria 3 through the Gemini API.

## Important: Not For Plagiarism / 不是用來剽竊

This project is for **music style study, education, composition research, and lawful creative ideation**.

It is **not** for:

- copying another song's melody, lyrics, hook, arrangement, or recording;
- making a soundalike that impersonates a real artist;
- rewriting copyrighted songs with slightly changed words;
- generating a commercial substitute for an existing song;
- bypassing copyright, license, or platform rules.

這個工具的用途是研究音樂風格、分析編曲和聲音特徵、幫助創作新的原創作品。它不是用來剽竊、仿冒歌手、複製旋律、改寫歌詞，或做出和原曲混淆的作品。

The prompt builder always adds this safety clause:

> Avoid copying any existing melody, lyric, hook, artist voice, or arrangement signature.

## What It Does

The pipeline now has four steps:

1. **Analyze** a local audio file with Essentia.
2. **Annotate style** with a reviewed `style_profile.json` that describes genre, instrumentation, groove, vocal style, arrangement, mood, and production texture.
3. **Build** a broad, non-infringing "music DNA" prompt from Essentia numbers plus the reviewed style profile.
4. **Generate** a new 30-second MP3 clip with Google Lyria 3 Clip.

Default input:

```text
input/reference.mp3
```

Default outputs:

```text
outputs/reference_essentia.json
outputs/generated_prompt.txt
outputs/lyria_response.txt
outputs/lyria_clip.mp3
outputs/lyria_error.txt
style_profile.json
```

## Requirements

- macOS or Linux shell
- Python 3.12 recommended
- `ffmpeg` for audio conversion if needed
- Google AI Studio / Gemini API key
- Python packages in `requirements.txt`

The project uses Python Essentia as the reliable fallback because Homebrew may not provide an `essentia` formula on every machine.

## Setup

```bash
cd music_dna_google
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Create a local `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and add your Google AI Studio key:

```bash
GEMINI_API_KEY=your_key_here
```

Do not commit `.env`.

## Style Profile

The first version of this project used a generic prompt template. That was not enough: Essentia can identify useful numeric traits such as BPM and key, but it does not reliably describe genre, vocal delivery, instruments, arrangement, or production style.

This version requires a style profile before generation. That prevents the system from falling back to hardcoded defaults such as gospel, choir, or piano when the reference track is a different style.

Create one manually:

```bash
cp style_profile.example.json style_profile.json
```

Edit `style_profile.json` so it accurately describes the reference track at a broad style level.

Or draft one with Gemini audio analysis:

```bash
.venv/bin/python annotate_style_with_gemini.py \
  --input input/reference.mp3 \
  --output style_profile.json
```

Always review the generated style profile before running the final generation step. The style profile should describe broad musical traits only; it should not name an artist to imitate, copy lyrics, or request a soundalike.

## Usage

Put a reference song here:

```bash
mkdir -p input
cp /path/to/reference.mp3 input/reference.mp3
```

Run the full pipeline:

```bash
./run_pipeline.sh
```

Or pass a file directly:

```bash
./run_pipeline.sh /path/to/reference.mp3
```

## Full Song Mode

For a full-song demo, use the `lyria-3-pro-preview` flow. This is separate from the 30-second clip pipeline.

Source assets:

```text
briefs/gate_b28_song_brief.json
lyrics/gate_b28_lyrics.md
```

Build the full-song prompt without calling Lyria:

```bash
.venv/bin/python build_full_song_prompt.py \
  --brief briefs/gate_b28_song_brief.json \
  --lyrics lyrics/gate_b28_lyrics.md \
  --style-profile style_profile.json \
  --output outputs/full_song_prompt.txt
```

Run the full-song pipeline:

```bash
./run_full_song.sh
```

The full-song flow asks Lyria Pro to use the provided Traditional Chinese lyrics verbatim where possible, not translate to English, and not use pinyin. Because Lyria may still shorten or rewrite lyrics, the pipeline writes a lyric-adherence report:

```text
outputs/lyric_adherence_report.txt
```

## Post-Mix / Mastering Assist

Lyria cannot guarantee DAW-level mix parameters such as exact compressor chains, mono 808, sidechain ducking, de-essing bands, or exact reverb tails. This project includes a post-production assist layer for measurable delivery checks.

Default master-only mode:

```bash
./run_post_mix.sh outputs/lyria_full_song.mp3
```

Outputs:

```text
outputs/lyria_full_song_mastered.wav
outputs/lyria_full_song_mastered.mp3
outputs/mastering_report.json
```

The master-only path uses FFmpeg loudness normalization toward the project target in `mix_specs/gate_b28_mix_spec.json`, then validates loudness, peak, duration, stereo correlation, and detected silence gaps.

Optional stem mode:

```bash
./run_post_mix.sh outputs/lyria_full_song.mp3 --stems
```

Stem mode requires `demucs` installed separately. It is approximate because stem separation from a mastered MP3 can create artifacts and bleed. Use it only for demo improvement, not as a substitute for real multitrack mixing.

No-MIDI audio ducking mode:

```bash
./run_post_mix.sh outputs/lyria_full_song.mp3 --audio-ducking
```

This runs a pure-audio sidechain pass before mastering:

- detects kick / low-frequency trigger events from audio, not MIDI;
- applies spectral low-band ducking by default;
- writes `outputs/lyria_full_song_ducked.wav`;
- writes `outputs/ducking_report.json`;
- then masters the ducked WAV to the normal WAV/MP3 outputs.

If you have a cleaner drum or kick stem, use it as the sidechain:

```bash
SIDECHAIN_PATH=outputs/stems/drums.wav \
./run_post_mix.sh outputs/stems/bass.wav --audio-ducking
```

For a more obvious pump, use envelope mode:

```bash
AUDIO_DUCK_MODE=envelope ./run_post_mix.sh outputs/lyria_full_song.mp3 --audio-ducking
```

This is designed to close the practical gap between Lyria output and DAW-side mix control without using MIDI. It approximates Trackspacer/Soothe2-style frequency unmasking with local DSP, but it cannot perfectly duplicate commercial plugin behavior or recover clean kick/808/Rhodes separation from a single mixed MP3.

## Individual Commands

Analyze only:

```bash
.venv/bin/python analyze_with_essentia.py \
  --input input/reference.mp3 \
  --output outputs/reference_essentia.json
```

Build prompt only:

```bash
.venv/bin/python build_prompt.py \
  --analysis outputs/reference_essentia.json \
  --style-profile style_profile.json \
  --output outputs/generated_prompt.txt \
  --title "reference song"
```

Write a starter style profile template:

```bash
.venv/bin/python build_prompt.py \
  --write-style-template \
  --style-profile style_profile.json
```

Generate with Google Lyria 3 Clip:

```bash
.venv/bin/python generate_lyria_clip.py \
  --prompt outputs/generated_prompt.txt \
  --audio-output outputs/lyria_clip.mp3 \
  --text-output outputs/lyria_response.txt \
  --error-output outputs/lyria_error.txt
```

## How The Prompt Is Built

The prompt builder combines numeric descriptors from Essentia:

- tempo / BPM
- tonal center and scale
- rhythm and danceability
- spectral brightness / timbre
- RMS and dynamic complexity
- broad arrangement suggestions
- safe originality clause

with reviewed style descriptors from `style_profile.json`:

- genre and scene
- mood
- instrumentation
- groove
- vocal or lead style
- arrangement arc
- production texture
- avoid notes

It does **not** extract or reuse lyrics, melody, hooks, or isolated copyrighted material.

## Recommended Workflow For Studying A Song

1. Use a lawful copy of a reference song.
2. Run Essentia analysis.
3. Read `outputs/generated_prompt.txt`.
4. Remove anything that feels too close to a specific song identity.
5. Generate a short clip.
6. Reject any output that sounds like a cover, imitation, or direct derivative.

## Rejection Checklist

Reject a generated result if:

- the main melody is recognizably the same as the reference;
- the chorus hook copies the rhythm or phrase shape of the reference;
- the lyrics paraphrase known lyrics;
- the vocal identity resembles a specific real singer;
- the arrangement has the same distinctive entrance order or dramatic signature;
- a reasonable listener would call it a copy, cover, or soundalike.

Accept only if:

- the output shares broad genre or mood traits;
- melody, lyrics, hook, and arrangement are new;
- the reference served as study material, not source material.

## Google Lyria Notes

This project uses:

```text
lyria-3-clip-preview
```

Google's Lyria 3 Clip model generates 30-second MP3 clips through the Gemini API. The response may include both text parts and audio parts, so the script iterates through all returned parts and saves the audio inline data when available.

Official docs:

https://ai.google.dev/gemini-api/docs/music-generation

## Privacy And API Keys

- API keys are read from `GEMINI_API_KEY` or `GOOGLE_API_KEY`.
- `.env` is ignored by git.
- The scripts do not print or save your key.
- API errors are written to `outputs/lyria_error.txt`.

## Project Status

Prototype / research tool. Use carefully and review generated output before sharing or publishing.
