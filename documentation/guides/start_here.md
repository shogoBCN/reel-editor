# Start here (read this first)

This repo turns a **talking-head video + a brief** into a 9:16 Instagram/Facebook reel (overlays, karaoke captions, fade, contact endcard).

You do **not** edit `compose.py` per client. You add a project folder and a brief.

```text
Phone recording  +  Excel brief (or YAML)  +  PNG stickers
                         ↓
              pipelines/reel_compose.py  (this engine)
                         ↓
              1080×1920 mp4  +  preview JPEGs
```

## Two clocks (the only concept that bites)

| Clock | Whose? | Example |
|-------|--------|---------|
| **Source** | Angélica’s original file, including opening silence | fruit bowl at `0:28` |
| **Final** | Published reel after `trim_start` | same bowl at `0:24` if trim is `4.0s` |

The brief always uses **source** time. Do not cut the recording; «El reel empieza en» is `trim_start`. `scripts/check_brief.py` prints both clocks.

## Where to look

| I want to… | Open |
|------------|------|
| Run the example | `examples/ya_tienes/` + commands below |
| Change Dra. Angélica colours / endcard | `brands/dra_angelica/` |
| Change canvas / safe zones / Gemini models | `config/config_store.py` |
| Put the Gemini API key | `auth/auth-config.json` (copy the example) |
| Change overlay motion / placement rules | `modules/video/overlays.py` |
| Change karaoke | `modules/video/captions.py` |
| Understand a pipeline | [`pipelines/README.md`](../../pipelines/README.md) |
| Give Angélica a form | `templates/angelica_brief/` |

## Commands (conda `angelica-website`)

```bash
conda activate angelica-website
pip install -r requirements.txt

python scripts/test_timing.py
python scripts/test_sticker_size.py
python scripts/check_brief.py --project examples/ya_tienes
python pipelines/reel_compose.py --project examples/ya_tienes --preview
```

`--full` encodes the mp4 (minutes). Preview first.

## Data vs engine

- **Brief** (`brief.yaml`, after Cursor maps her Excel) = *when* and *which file*.
- **Brand pack** = *how it looks* (teal brush, fonts, endcard).
- **Engine** = trim, composite, captions, fade. Shared by every reel.

YAML on disk still uses short keys (`asr_fix`, `max_w`, transcript `w`/`s`/`e`) so existing sheets keep working. Python names inside the engine are fully spelled out.
