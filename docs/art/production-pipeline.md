---
version: "1.0.0"
schema_version: 2
title: "Badge Production Pipeline"
doc_type: detail
parent: INDEX.md
last_updated: 2026-08-19
last_audit: 2026-08-19
audit_status: current
domain: docs
triggers:
  - "badge pipeline"
  - "generate badge art"
  - "orientation gate"
  - "badge LOD"
---
# Badge Production Pipeline

**Five deterministic stages take a badge concept to shippable assets: prompt, render on both models, orientation gate, grade and tag, emit level-of-detail set.** Every failure mode found during the pilot has a mechanical guard in this chain, so quality does not depend on inspecting 48 images by eye.

## Stages

| # | Stage | Tool | Guarantee |
|---|---|---|---|
| 1 | Prompt | `prompt_<slug>.txt` | template v3.1 + focus mode + canonical direction, textless |
| 2 | Render | `gen_grok.py` (xAI `grok-imagine-image-quality`), Codex built-in `image_gen` | square masters from two models on identical prompts |
| 3 | Orientation gate | `check_orientation.py`, `orientation_gates.sh` | canonical direction enforced, auto-mirrored when violated |
| 4 | Grade | `postprocess.py` | saturation +18%, contrast +6%, Display P3 profile |
| 5 | LOD emit | `postprocess.py` | `icon_1024`, `icon_72`, `icon_32` per badge per model |

Scripts live beside the assets at `/Volumes/WD Black (2TB)/Game Dev/scratch/llm-grader/badge-art/`.

## Stage detail

**Render.** Both lanes take the identical prompt so a later vote measures the model, not the prompt. The xAI lane accepts `aspect_ratio: "1:1"` natively and returns 1024×1024; the Codex lane is instructed to render square and is normalised in stage 4 regardless. The xAI driver is a Python script rather than shell: an early shell version silently produced 21 empty files because nested quoting broke the JSON payload, which is why the driver now owns the request end to end and retries once per image.

**Orientation gate.** For direction-critical badges, a vision model answers a strict yes/no question about layout ("are the craters in the left half with the knight on the right?"). A `NO` triggers a lossless horizontal mirror; an unparseable answer leaves the file untouched and flagged rather than guessing. This is only safe because the art is textless — mirroring a painted nameplate would destroy it.

**Grade and LOD.** Masters are center-cropped square and resized to 1024. The 32 px asset is not a naive downscale: it is a 62% center-zoom crop with additional contrast and saturation, because at tile size a full-frame composition loses its subject. All three levels carry the P3 profile.

## Running it

```bash
cd "/Volumes/WD Black (2TB)/Game Dev/scratch/llm-grader/badge-art"
export XAI_KEY=$(aws ssm get-parameter --name /shared/api-keys/xai \
  --with-decryption --region us-east-2 --query Parameter.Value --output text)

python3 gen_grok.py <slug> [<slug> ...]      # xAI lane
bash orientation_gates.sh                     # direction gate + auto-mirror
python3 postprocess.py                        # grade, P3 tag, LOD set
open gallery.html                             # blind A/B review
```

The Codex lane runs per badge and must be anchored at a directory containing an instruction file, reaching the scratch directory through `--add-dir`, with stdin closed:

```bash
codex exec -C "$HOME/repos/personal/Game Dev" --add-dir "$PWD" \
  -s workspace-write --enable image_generation \
  "Generate one image with the image_generation tool and save it to exactly this path: $PWD/chatgpt_<slug>.png — then stop. The image MUST be square (1:1). Image prompt: <prompt>" < /dev/null
```

## Cost and volume

One image per badge per model — 48 masters, 144 derivatives. Variants are a winners-only second pass, deliberately: rendering three variants of a losing badge wastes budget. The Codex lane is subscription-billed at no marginal cost; the xAI lane is metered at cents per image.

## Known fragilities

- Image models occasionally return a malformed response; the driver retries once, then reports and continues rather than aborting the batch.
- The orientation gate depends on a vision model's yes/no discipline; an ambiguous answer is treated as "leave alone", never as a mirror.
- Codex renders are slower than the API lane by roughly an order of magnitude, so batches run in the background.
