# dcv — Photo Library Compressor (AV1-backed)

**Compresses a folder of photos by ~90 %+ with no visible quality loss, by finding near-duplicate images, grouping them, and encoding each group as a short AV1 video. Single images become AVIF.**

Real-world result on a 150-photo sailing shoot: **576 MB → 32 MB (−94 %)**, fully reversible, ~1 % average per-pixel deviation (visually identical). On heterogeneous stock collections: **−60 %**. On a single 43-photo folder: **329 MB → 24.5 MB (−92.6 %)**, every image reconstructed.

This is **not a new codec.** It orchestrates [AV1](https://en.wikipedia.org/wiki/AV1) (via ffmpeg). The contribution is the part AV1 doesn't do: discovering the hidden similarity graph in an unordered photo library, grouping similar shots, and feeding each group to the encoder so its inter-frame prediction does the work.

---

## What it does

1. **Cluster discovery** — reconstructs which photos are near-duplicates (shape -> histogram cosine -> thumbnail energy, union-find). Runs on lightweight metadata, not full images, to keep RAM low.
2. **Ordering** — orders frames in a cluster by similarity (`greedy`; `tree`/MST also available).
3. **Encoding** — clusters of >=2 images -> one AV1 video; singletons -> AVIF. Edge-heavy images auto-route to 4:4:4 chroma.
4. **Fallback** — if the AV1 path isn't smaller than the originals, keeps the originals. Output is never larger than input.
5. **Roundtrip** — decoded images are written as PNG (no second lossy step).

Two quality modes:
- **Lossy (default):** ~90 % smaller, ~1-1.5 % average deviation (invisible to the eye).
- **Lossless (`--lossless`):** bit-exact (0 % deviation, verified), but only ~20-40 % smaller on real photos. Uses RGB (gbrp) + `lossless=1` to avoid the YUV rounding that breaks bit-exactness.

---

## Install

Requires **Python 3.9+** and **ffmpeg with libaom-av1** (libsvtav1 recommended for speed).

```bash
pip install -r requirements.txt
```

**ffmpeg:**
- Linux: `sudo apt install ffmpeg`
- macOS: `brew install ffmpeg`
- Windows: a build with **working** SVT-AV1 is recommended — use [BtbN builds](https://github.com/BtbN/FFmpeg-Builds/releases) (`ffmpeg-master-latest-win64-gpl.zip`). The `install_ffmpeg.ps1` / `update_ffmpeg_svt.ps1` helpers automate this.

**Verify:** `ffmpeg -encoders | grep av1` should list `libaom-av1`. For speed, `ffmpeg -h encoder=libsvtav1` should print encoder options (not an error).

---

## Usage

```bash
# See what it does (read-only; appends a benchmark_log.txt next to the script)
python stockphoto_video.py benchmark --root /path/to/photos --crf 28

# Compress, then restore
python stockphoto_video.py compress    --root /path/to/photos --out library.dcv --crf 28
python stockphoto_video.py decompress  --archive library.dcv --out restored/

# Measure exact deviation in plain percent (original vs reconstruction)
python stockphoto_video.py vergleich   --a /path/to/photos --b restored/
```

`--root` points at a folder; immediate subfolders are treated as separate collections (use `--global` to cluster across all of them).

### Options

| Flag | Default | Meaning |
|---|---|---|
| `--crf N` | 28 | Quality. Lower = better/larger. 22 ~ JPEG q95, 28 ~ q85, 34 ~ q75. (On photos, CRF barely changes deviation — it mostly changes size.) |
| `--encoder libaom\|svt` | libaom | `svt` is far faster on multi-core machines. Self-tests at startup; falls back to libaom if SVT is broken in your ffmpeg build. |
| `--speed N` | — | libaom cpu-used 0-8 / SVT preset 0-12. Higher = faster/larger. Try `--speed 10` or `12` for big runs. |
| `--order greedy\|tree\|none` | greedy | Frame ordering within a cluster. (`tree` rarely helps — see DEVLOG.) |
| `--edge-thr F` | 3.0 | Colour-edge density above which an image uses 4:4:4 chroma. Lower = 4:4:4 more often. |
| `--global` | off | Cluster across all subfolders (finds cross-folder duplicates). |
| `--lossless` | off | Bit-exact, 0 % deviation. Much larger. libaom only. |

---

## Performance notes

- **Encoding is ~78 % of the time** (measured). Loading and clustering are negligible.
- **libaom is slow on large images.** A 4.4 GB / 1154-photo `--global` run hit a ~14 h estimate. Use `--encoder svt --speed 10+`, and/or process folder-by-folder rather than one giant `--global` run.
- **Old GPUs don't help.** AV1 hardware encoding needs RTX 40-series (2022) or newer. Maxwell/Turing (GTX 850M, T4) have no AV1 encoder.
- **Memory-safe:** clustering uses thumbnails + histograms, full images load only per-cluster (~200 MB peak observed). A startup RAM check warns on large runs.

---

## Honest limitations

- **Lossy by default** (~1-1.5 % average per-pixel deviation; invisible, but not bit-exact). MAE bounds the *average*, not the worst pixel. Fine for stock/web/archival; **not** for forensics, medical imaging, or pixel-diffing. Use `--lossless` for 0 %.
- **Savings depend on your data.** Best with near-duplicates (bursts, product shots). Distinct, texture-heavy photos fall to the ~40-50 % AVIF singleton floor.
- **Format dependency:** decoding needs ffmpeg/AV1. Royalty-free and widely supported, but a dependency to note for long-term archival.

See `DEVLOG.md` for the full development log — every hypothesis tested, including the ones that **failed** (reference trees, synthetic seeds, second-order deltas, lossless I-frames). Kept in for honesty and to save the next developer from re-treading dead ends.

## License

MIT — see `LICENSE`.

## Acknowledgements & third-party software

This tool does **not** include or redistribute any of the following — it calls a user-installed `ffmpeg`. All credit for the actual compression goes to these projects:

- **[FFmpeg](https://ffmpeg.org/)** — the multimedia framework this tool drives. Licensed under LGPL-2.1-or-later (some optional parts GPL). FFmpeg is a trademark of Fabrice Bellard. This tool uses FFmpeg via command-line invocation; it does not link against or bundle FFmpeg.
- **[libaom (AV1)](https://aomedia.googlesource.com/aom/)** — the AV1 reference encoder, by the Alliance for Open Media (BSD-2-Clause). Does the heavy lifting of the actual encoding.
- **[SVT-AV1](https://gitlab.com/AOMediaCodec/SVT-AV1)** — the faster AV1 encoder (BSD-3-Clause-Clear), also by the Alliance for Open Media.
- **AV1** is a royalty-free codec developed by the Alliance for Open Media (Google, Mozilla, Amazon, Netflix, and others).

Python dependencies: NumPy, Pillow, SciPy, psutil — see `requirements.txt`.

The original work in this repository (clustering, orchestration, archive format, CLI) is licensed under MIT — see `LICENSE`.

By Felix Zipp
