# Gate B28 Failed Try - 2026-06-17

Status: failed try / not accepted for production use.

## Input

- Active lyrics file: `lyrics/gate_b28_lyrics.md`
- Production brief: `briefs/gate_b28_song_brief.json`
- Style profile: `style_profile.json` local only, not committed
- Generation path: Lyria full-song pipeline, followed by no-MIDI spectral ducking and mastering

## Generated Local Files

These files were generated locally and are intentionally not committed because `outputs/` is ignored:

- `outputs/lyria_full_song.mp3`
- `outputs/lyria_full_song_response.txt`
- `outputs/lyria_full_song_ducked.wav`
- `outputs/lyria_full_song_mastered.wav`
- `outputs/lyria_full_song_mastered.mp3`
- `outputs/lyric_adherence_report.txt`
- `outputs/ducking_report.json`
- `outputs/mastering_report.json`

## Measured Result

- Duration: 179.46 seconds
- Lyric line overlap: 83 / 83
- Audio ducking trigger events: 198
- Integrated loudness: -13.94 LUFS
- True peak: -1.45 dBTP
- Loudness validation: passed
- True peak validation: passed

## Failure Note

The attempt is marked failed by user review despite passing mechanical lyric-adherence and mastering checks. The current pipeline can verify text overlap and measurable delivery targets, but it still cannot guarantee subjective production fit, emotional delivery, vocal tone, groove, or arrangement quality from the model output.

## Follow-Up Gap

Before another generation attempt, improve one or more of:

- stronger style annotation and production prompt constraints;
- stem-based post-processing instead of full-mix ducking;
- human review checkpoint before accepting a generated take;
- external DAW or stem workflow for vocal/bass/drum control.
