# Registered DCT comparison (step 6 continuation)

This experiment tests two lower-strength QIM candidates and a small geometry search. It preserves the earlier baseline code, harness, stress plans, and results.

```sh
python3 -m unittest discover -s benchmark/tests -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -m benchmark.conventional_registered --out benchmark/runs/conventional-v2-replay
```

Use a fresh output directory. The runner uses exactly the same 24 tuning sources, 128-bit test IDs, and 100 negative candidates recorded by v1. Source files must have been restored locally. It checks the source lock, reviewed tuning eligibility, source selection, and test-ID format before evaluation. It records hashes of the new candidate, its unchanged baseline helper, runner, prior plan, source manifest, and visual review.

## Candidate changes

`qim12_registered` and `qim20_registered` quantize luminance coefficient (1,2), using steps 12 and 20 respectively. The payload remains the full 176-bit frame: 16-bit experimental marker, 128-bit test ID, and 32-bit CRC. Repetition, majority voting, and CRC validation are unchanged. Lower distortion is a hypothesis until measured. Several factors changed together from v1 (coefficient, strength, and search), so the comparison is not a one-variable attribution experiment.

The extractor only receives pixels and candidate configuration. It searches at most four views:

1. The full image at its supplied resolution.
2. The full image resampled to a 1024-pixel long edge, if its size differs.
3. A region obtained by removing contiguous, exactly uniform outer bands matching the corner color, when detected.
4. That region resampled to a 1024-pixel long edge, if needed.

All views are attempted, including after an ID is found. Conflicting IDs are preserved and the existing scorer counts ambiguous recovery as failure. A view with insufficient capacity is logged as skipped; the remaining declared views still run. Each prediction records geometry, rectangle, view size, status, and any decoded ID. The complete search is applied to negative candidates too, rather than testing only the easiest negative geometry.

Uniform-border removal uses no known margin dimensions, fixed background color, source ID, or expected payload. Tests include an asymmetric border with a different color from the harness. It can still trim genuine scene content and is **not** a general screenshot-region detector. Any discovered rectangle is only a recovery hint; it never changes the full input's recorded SHA-256 or the production integrity contract.

The fixed 1024 target is a declared tuning assumption: all positive sources in this comparison have that long edge. Decoder resampling is a search operation and does not create native-resolution eligibility. Arbitrary source sizes, crop offsets, rotation, app controls, compressed/nonuniform borders, perspective, and physical display/camera effects remain unqualified.

## Evidence and interpretation

The [v2 plan and results](reports/conventional-v2/comparison.json) retain all failures and per-transform/size buckets. Synthetic canvases stay synthetic; successful border removal must not be described as successful real Android screenshot recovery. Negative-source approval is still pending, and 100 negative sources do not establish the release false-positive target.

All software dependencies remain those inventoried in [v1](reports/conventional-v1/dependency-license-inventory.json); no model, additional watermark package, or paid service was introduced. The repository's outbound-license decision and Android implementation remain pending. Desktop timings are not Android measurements. The local environment check found Java but no `adb` on PATH or at the default Windows Android SDK location; it does not establish whether the user owns or can borrow a suitable phone.

The completed run pins BLAS/OpenMP to one thread and SciPy FFT workers to one. The earlier v1 run did not pin BLAS thread counts, so cross-version timing is descriptive rather than a controlled speed comparison. A preliminary v2 run was stopped before any candidate completed and is excluded from published results.

## Measured outcomes

Both candidates completed 796 cases: 24 × 29 positive transforms and 100 negative candidates. This is 1,592 new cases, not 1,592 independent photos. All searches remained within the four-view budget.

| Measurement | `qim12_registered` | `qim20_registered` |
| --- | --- | --- |
| Original full-ID recovery | 24/24 | 24/24 |
| JPEG Q70 | 23/24 | 23/24 |
| JPEG Q50 | 23/24 | 24/24 |
| 512-pixel resize | 21/24 | 21/24 |
| 1024-pixel synthetic screenshot | 24/24 | 24/24 |
| 512-pixel synthetic screenshot | 21/24 | 21/24 |
| Each crop / rotation condition | 0/24 | 0/24 |
| Synthetic combined chain | 0/24 | 0/24 |
| Mean SSIM | 0.99127 | 0.97885 |
| Fifth-percentile SSIM | 0.98714 | 0.96712 |
| Proposed numerical quality floor met on this tuning subset | Yes | No: mean below 0.98 |
| Negative detections | 0/100 | 0/100 |
| Desktop embed + encode p95 | 85.09 ms | 48.67 ms |

The gentler candidate is the more promising direction from this comparison: the stronger setting gives no gain in 512-pixel recovery and misses the proposed mean-quality floor. This is not production selection or completion of the QA4 gate; blinded display review, broader data, and physical measurements are outstanding. The change improves synthetic border/scale handling, while every crop and rotation bucket still fails. Both also fail every 256-pixel case. The 1024/2048 resize transforms remain no-ops for these 1024-pixel source images.

The first export and five transformed inputs per candidate reproduced byte-for-byte. Their decoded ID sets and complete attempt records also matched. All 40 automated tests pass. Per-bucket timings and source/input hashes remain in the detailed reports; any pooled timing statistic is descriptive only.

Continue with crop/rotation synchronization and broader tuning coverage before freezing a candidate. Physical Android screenshot and cost evidence remain required. Step 6 stays **In progress**.
