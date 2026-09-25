# Photo benchmark harness

Free, local research tooling for roadmap goal 5. It prepares test inputs and scores externally supplied decoder results. It contains **no watermark algorithm, production canonicalizer, attestation client, or cryptographic verifier**.

## Current corpus

The locked starter manifest has 1,200 locally downloaded Open Images sources: **100 tuning, 1,000 reserved held-out, and 100 negative candidates**. Each selected source has a different author group. Byte and decoded-pixel duplicates were excluded; visual near-duplicate review remains pending. The manifest preserves author, title, original landing page, dataset-declared license, download URL, dimensions, and SHA-256. Media and generated runs are ignored by Git; only attribution/inventory and reports are committed.

Open Images publishes per-image license and attribution metadata and an official method for retrieving subsets from CVDF. The selected rows declare CC BY 2.0. This is dataset-declared eligibility, not an individual license verification or consent determination. Consult [the official dataset download documentation](https://storage.googleapis.com/openimages/web/download_v7.html) and each manifest entry's source/attribution before redistribution. The sources are unmodified CVDF copies locally; benchmark outputs are derivatives whose operations are recorded.

The acquired copies have long edges of 768–1024 pixels (1,187 are at least 1024). They do not cover native 2048-pixel testing; add freely available higher-resolution sources rather than upscaling.

**This is not the release corpus.** Rights/content review, category coverage, actual screenshots, and the 300,000-input false-positive suite remain pending. Existing marks on external images have not been manually ruled out. Held-out means reserved from model tuning; the manifest is byte-locked but not approved for final release evaluation. Do not inspect candidate performance on it until candidate, thresholds, and search procedure are frozen.

## Setup and restore

Run from the repository root. Python 3.10+ is required. Dependencies are pinned in `benchmark/requirements.txt`; the recorded run used the versions shown in its environment report.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r benchmark/requirements.txt
.venv/bin/python -m benchmark.corpus
.venv/bin/python -m benchmark.harness audit benchmark/manifests/openimages-starter.jsonl
.venv/bin/python -m unittest discover -s benchmark/tests -v
```

With an existing manifest, the acquisition command downloads missing sources from the fixed public CVDF host and checks original SHA-256 values. It refuses changed bytes instead of silently changing the cohort. It requires no account, paid API, or GPU. Initial acquisition without a manifest uses deterministic author-based splitting and records exclusions; create a new version deliberately rather than changing an existing snapshot. Original source metadata is fetched from the fixed official host only.

Keep at least 0.5 GB free for the starter media and more for generated runs. Generate small tuning batches first; transformations can consume substantially more storage than originals. Images/metadata remain local unless explicitly shared. Do not commit participant media or private metadata to this public repository.

## Prepare repeatable input cases

```sh
python3 -m benchmark.harness build benchmark/manifests/openimages-starter.jsonl \
  --split tuning --limit 8 --out benchmark/runs/my-smoke
```

The output directory must not exist. There are **29 transformations per source**:

- Original and metadata removal (APP1/APP13/comment removal without re-encoding; rendering markers retained).
- JPEG Q90/Q70/Q50, pinned Pillow JPEG settings and codec environment.
- Long-edge 2048/1024/512/256 resize; never upscale a small source.
- 75%, 50%, and 25% area crops at center, top-left, and bottom-right; rounded dimensions recorded.
- ±5° rotations (same canvas, black fill), lossless 90° geometry in PNG output, gamma 0.8/1.2, brightness ±10%, and a white overlay on the top 10% of area.
- **Synthetic** screen canvases at media long-edge 512/1024 and synthetic screen → 75% center crop → 1024 resize → Q70. These are not evidence for actual screenshot or actual combined-screenshot gates.

Geometry/color results use lossless PNG unless the case explicitly specifies JPEG. Research preprocessing applies EXIF orientation, converts an existing valid ICC profile to sRGB, composites alpha on white, caps at 2048 pixels, and creates a Q95 4:2:0 JPEG. CVDF's downloaded orientation is used after EXIF handling; the source's dataset rotation is retained for review but not blindly reapplied. Sources shorter than a case's target edge cannot qualify as 1024+ or 2048 native-resolution evidence. Each result records actual output dimensions.

`run.json` pins the manifest, harness hash, Python/Pillow/numpy/scipy versions, JPEG library, source count, encoder settings, and cases hash. `cases.jsonl` records transformed bytes/pixel hashes and expected identifiers. The research pixel hash is domain-separated and dimension-bound; it is not INT1's future production definition.

Without `--exports`, tuning runs are explicitly **unwatermarked harness smoke tests**. They cannot measure watermark recovery. Negative split runs are negative candidates and require eligibility review before release use. The held-out split requires `--allow-heldout`, a deliberate procedural override to use only after candidate freeze. This flag alone does not establish approval.

## Candidate adapter contract (goal 6)

Create watermarked final JPEGs externally, then supply a JSONL manifest through `build --exports path/to/exports.jsonl`. Every selected source must have exactly one entry:

```json
{"source_id":"oi-IMAGE_ID","path":"exports/example.jpg","sha256":"SHA256_OF_FINAL_JPEG","expected_id":"0123456789abcdef0123456789abcdef"}
```

Paths are relative to that exports manifest. Assign per-asset IDs at embedding and retain them in the manifest. Never count a partial ID as a successful recovery. Do not silently truncate identifiers to fit a candidate: revise the benchmark contract and payload design explicitly if goal 7 changes the identifier scheme. Negative inputs cannot be supplied watermarked exports.

Pass `build --device DEVICE_LABEL` to identify the actual decoder execution device; dataset capture origin is stored separately. Candidate metadata must match that scheduled device. The default is `desktop-local-unqualified`, never an Android performance claim.

Run the candidate's **entire declared decoder search** once for every scheduled case and record one result per case:

```json
{"case_id":"oi-IMAGE_ID__jpeg_q70","status":"ok","search_complete":true,"detected":true,"decoded_ids":["0123456789abcdef0123456789abcdef"],"elapsed_ms":143.2}
```

Allowed status: `ok`, `error`, `timeout`, `unsupported`. An `ok` result requires complete search; report detection separately from complete-ID decoding. Keep all candidate IDs after calibrated thresholding, not just a cherry-picked correct crop. Multiple copies of the same ID count once; a result containing any wrong ID does not count as correct recovery. Missing/error/timeout cases stay in the denominator. Timing covers the full search, not one attempt.

Populate `candidate-metadata.example.json` with immutable code/weights versions, payload/ECC, thresholds, search budget, actual runtime/device, and licenses. The harness records this declaration; it does not independently verify that an adapter honors it. Do not leave template placeholders in a real report.

```sh
python3 -m benchmark.harness score benchmark/runs/my-run/cases.jsonl predictions.jsonl \
  --candidate-metadata candidate.json --out benchmark/runs/my-run/results.json
```

Reports retain separate transform/device/size/input-kind buckets, complete/missing counts, correct IDs, wrong IDs, detections, p95 full-search time, and Wilson 95% intervals. For a fully evaluated negative bucket with zero detections, report the exact one-sided binomial 95% upper bound `1 - 0.05**(1/N)` and approximate `3/N`. No zero-event bound is issued for incomplete searches. These bounds assume representative independent inputs; variants of one photo are correlated, and the harness never pools all transforms into a fake 300,000-independent-source result. Wrong-record lookup and false cryptographic acceptance are explicitly **not measured** by this detector harness.

## Quality comparisons

```sh
python3 -m benchmark.harness quality baseline.jpg watermarked.jpg --out quality.json
```

Use equal-size final exports with identical encoder settings; only watermark embedding should differ. SSIM uses RGB channel averaging, an 11×11 Gaussian window, sigma 1.5, population moments, valid interior, and range 255; PSNR is also recorded. An identical image has SSIM 1 and infinite PSNR (serialized as null with an explanation). This is one pair's measurement. Aggregate over the frozen source cohort before comparing mean and fifth-percentile QA4 targets; blinded display review remains required. Transform robustness images are not the visual-quality baseline.

## Real screenshots and final readiness

`screenshot-intake.csv` is a blank intake schema, not fabricated evidence. Each actual screenshot must retain parent source/asset ID, split, byte hash, device/OS/app versions, display scale, media size, borders, crop-selection method, and permission basis. Screenshots of the same source stay in its split. Capture the selected watermarked export through a real display pipeline after goal 6; no screen can contain a candidate watermark before that candidate exists.

Use the readiness checklist in [goal 5](../docs/05-benchmark-data-and-harness.md). Do not mark release gates passed merely because unit tests or harness smoke runs pass.
