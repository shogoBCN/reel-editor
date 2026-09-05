# Prepare overlays

Cut near-black backgrounds from PNG stickers (phone screenshots, emoji packs) and crop to the alpha bbox.

**Entry:** [`prepare_overlays.py`](../prepare_overlays.py)

```bash
conda activate angelica-website
python pipelines/prepare_overlays/prepare_overlays.py \
  --input-dir projects/mi_reel/overlays_raw \
  --output-dir projects/mi_reel/overlays \
  --thresh 28 --feather 1
```

Already-keyed assets (e.g. `examples/ya_tienes/overlays/`) do not need this step.
