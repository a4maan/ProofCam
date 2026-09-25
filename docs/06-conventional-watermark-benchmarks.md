# Step 6: Conventional watermark experiments

Status: **In progress**. This first desktop tuning experiment compares two conventional block-DCT baselines. It does not qualify an Android device, certify media, or select the production watermark.

## Candidates and payload

Both implementations are original research code in [dct_baseline.py](../benchmark/candidates/dct_baseline.py). They use SciPy's orthonormal two-dimensional [DCT and inverse DCT](https://docs.scipy.org/doc/scipy/reference/generated/scipy.fft.idctn.html) on 8×8 luminance blocks, with RGB luminance weights 0.299/0.587/0.114. Neither uses AI or model weights.

| Candidate | Embedding rule | Fixed parameter |
| --- | --- | --- |
| `pair24` | Enforce the sign of the difference between coefficients (2,3) and (3,2) | Minimum absolute difference 24 |
| `qim48` | Quantize coefficient (2,3) to an even or odd lattice index | Quantization step 48 |

Each frame carries `PC` (16 bits), a complete public test record ID (128 bits), and CRC32 over the first 18 bytes (32 bits): **176 bits total, with 48 bits of framing/checksum overhead**. The current marker identifies this experimental format; it does not provide a production issuer-routing field. One bit goes in each block, with the frame repeated in raster order. At least three full frames (528 blocks) are required. Remaining blocks repeat the start of the frame; incomplete pixel blocks at the image edges are left unchanged.

Extraction majority-votes each bit position across repetitions, rejects ties, and requires the exact marker and checksum. It receives only pixels and the chosen configuration, never the expected ID or source record. Repetition is the only error correction. CRC is error detection, not cryptographic authentication. Anyone with this public algorithm can embed or copy a payload; signed records and integrity checks remain separate requirements.

Search is exactly one attempt at the supplied image's native geometry, using the chosen candidate. There is **no scale, crop-offset, rotation, or screenshot-region search**. These deliberately simple baselines establish whether payload embedding works and expose synchronization failures. A successful original-image test is not evidence of screenshot resilience.

## Experiment protocol

```sh
python3 -m unittest discover -s benchmark/tests -v
python3 -m benchmark.conventional --out benchmark/runs/conventional-new-version --limit 24
```

The command refuses an existing output directory. It validates the locked starter corpus and visual-review references, then selects the first 24 sorted primary-photo tuning candidates. This small deterministic selection is not representative release evaluation. The 1,000 held-out sources are untouched. All 100 starter negative candidates receive an original-image search; their final eligibility is still unapproved.

Both candidates receive the same randomly generated 128-bit test IDs, saved in `plan.json` before embedding. Fresh runs generate fresh IDs; byte-for-byte replay uses the saved IDs, pinned source bytes, code hashes, and library versions. The run retains watermarked exports, export manifests, case input hashes, complete predictions, per-source quality, and scored buckets. Transformed inputs can be reconstructed from the retained exports with `harness.transform`. Downloaded media and generated exports stay local.

Each positive source runs all 29 existing transforms, including recompression, resize, crop, rotation, brightness/gamma, overlay, and explicitly synthetic screenshot canvases. The decoder receives the full synthetic canvas; no source-informed crop coordinates are provided. Unsupported inputs stay in the failure denominator. Results are separated by transformation and size. Repeated images across transformations are not independent samples.

Image quality compares identically encoded JPEG-Q95/4:2:0 unwatermarked and marked exports using RGB Gaussian SSIM and PSNR. Extraction timing excludes image decoding; embedding timing includes embedding and JPEG encoding but excludes loading/normalization. Both are Python desktop wall time, not mobile performance. Peak memory and perceptual human review are not measured.

## License and implementation inventory

The [installed dependency inventory](../benchmark/reports/conventional-v1/dependency-license-inventory.json) records exact versions, package metadata, and hashes of bundled license files for NumPy, SciPy, and Pillow. No model or third-party watermark implementation was downloaded. The repository does not yet declare an outbound code license; redistribution review and required notices remain pending. This inventory is not a patent clearance or an Android dependency selection. Python/SciPy are research tools, not the proposed Android shipping runtime.

## Initial measured results

The [pinned comparison](../benchmark/reports/conventional-v1/comparison.json) covers **796 searches per candidate**: 24 tuning sources × 29 transforms, plus 100 negative-candidate originals. Both completed; one too-small 256-pixel case per candidate was recorded as unsupported and retained in the denominator. All 37 automated tests pass. The first exported image and four transformed hashes per candidate reproduced exactly from saved test IDs and source bytes.

| Measurement | `pair24` | `qim48` |
| --- | --- | --- |
| Full-ID recovery, original exports | 24/24 | 23/24 |
| JPEG Q70 recovery | 23/24 | 24/24 |
| Recovery for each of nine crop conditions | 0/24 | 0/24 |
| Recovery after 512-pixel downscale | 0/24 | 0/24 |
| Recovery for each synthetic screenshot size (512, 1024) | 0/24 | 0/24 |
| Detections in 100 negative candidates | 0 | 0 |
| Mean RGB SSIM | 0.95595 | 0.89603 |
| Fifth-percentile RGB SSIM | 0.93887 | 0.84090 |
| Desktop embedding + JPEG encoding p95 | 52.50 ms | 40.81 ms |

**Neither baseline meets the proposed QA4 numerical quality floor** (mean SSIM ≥0.98, fifth percentile ≥0.95), nor the required geometric/screenshot recovery envelope. No candidate is selected for production. Zero detections in this small, unapproved negative cohort do not establish the release false-positive target. Detailed reports retain size-specific buckets and conditional confidence bounds.

All 24 selected positive sources have a 1024-pixel long edge. The harness never upscales, so `resize_1024` and `resize_2048` are no-ops here, not successful rescaling evidence. Real downscales fail. All three rotation conditions also recover 0/24 for each candidate. The occasional improvement under recompression or gamma is a tuning observation, not monotonic robustness.

Next research work should address geometric synchronization and reduce embedding distortion, then compare coding choices under the same full-ID requirement. The current measurements do not establish that conventional watermarking in general is infeasible. Native 2048-pixel variants and the rest of the tuning cohort remain untested by this run; held-out evaluation must wait for candidate freeze.

## Remaining gates

Continue tuning synchronization and coding, then freeze candidates and search budgets before held-out evaluation. Measure actual screenshots, complete-ID recovery, negative searches under the full declared budget, artifacts, and physical Android latency/memory. Rights and final corpus eligibility remain outstanding from step 5. No support envelope, release threshold, or physical-device result is inferred from this initial experiment.

## Registered-candidate continuation

[The second experiment](../benchmark/REGISTERED.md) tests `qim12_registered` and `qim20_registered`: gentler quantization at coefficient (1,2), plus up to four pixel-only native/rescaled/uniform-border views. It reuses v1's exact tuning sources and full test IDs and keeps all earlier evidence unchanged. Every search attempt and any conflicting recovered IDs are recorded. All 40 tests pass.

This remains a tuning study. Removing an exactly uniform synthetic border is not equivalent to locating media within a real phone UI. Resampling toward the known 1024-pixel tuning scale does not establish support for arbitrary capture dimensions. Actual screenshots, crop/rotation synchronization, and physical Android measurements remain outstanding.

The completed continuation adds **1,592 cases**. `qim12_registered` meets the proposed numerical quality floor on the 24-photo tuning subset (mean SSIM 0.99127, fifth percentile 0.98714). It recovers 24/24 original IDs, 24/24 1024-pixel synthetic screenshots, and 21/24 512-pixel synthetic screenshots. `qim20_registered` gives the same screenshot counts but misses the mean-quality floor. Both have 0/100 negative detections under their declared search, and both still fail all crop/rotation buckets. See the [comparison](../benchmark/reports/conventional-v2/comparison.json) and [protocol/results](../benchmark/REGISTERED.md). No production candidate or real-device support is selected.
