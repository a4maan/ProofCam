# Adaptive tiled candidate v3

`ios-tiled-adaptive-conv-v3` is the iPhone research app's default. V1 and v2 remain selectable; screenshot decoding follows the candidate saved with the run. Android is unchanged.

Each complete 132×120 tile carries a synchronization marker and the complete PC + 128-bit ID + CRC32 frame. A rate-1/2 convolutional code (constraint length 7, generators octal 171/133, six terminating zero bits) adds redundancy. Soft Viterbi decoding rejects ambiguous paths and invalid checksums. CRC is error detection, not authentication.

A lower-frequency DCT(1,1) carrier uses 6×6 cells and minimum-change sign embedding. Magnitude adapts from 12 to 60 with local luma variation. Existing adequate coefficients are preserved. Incomplete edge tiles remain unchanged. Floating-point luma processing and a separable coefficient recurrence support the search.

Recovery scans integer tile origins across whole-image and heuristic background crops, native/512/768/1024/half/double scales up to 1600 pixels, and eight rotations/reflections. Native half-pitch tiles are also searched. A whole-image angular search capped at 512 pixels covers −45° through +44.5° at half-degree steps, with both tile pitches and eight symmetries. The four strongest synchronization hypotheses receive quarter-degree refinement at up to 1024 pixels. Expected IDs are never passed to the decoder. All configured searches run, preserving conflicting IDs.

## Results

The frozen implementation recovered 125/125 marked cases: 25 transforms on three development sources plus two additional photos selected before evaluation. It fixes the six v2 misses: crop then half-size on two sources, 7.3° rotation on one, and 20° rotation on all three. There were no detections on 100 procedural noise negatives or unexpected IDs. This does not establish a real-photo false-positive rate.

Raw RGB photo SSIM changed from 0.941→0.958, 0.912→0.950 and 0.947→0.962. PSNR is not uniformly improved, and procedural noise distortion is worse. These scores do not establish invisibility or Apple JPEG quality.

Median host recovery was 4.392 seconds, p95 6.903 seconds, maximum 8.953 seconds across 225 cases. The broader search costs more than v2. Twenty measured app iterations plus warmups may take substantial time; host results do not predict phone speed.

See [all cases](../benchmark/reports/step06-ios-adaptive-simulation.json) and [comparison and quality](../benchmark/reports/step06-ios-adaptive-comparison.json). Reports retain all outcomes and source/input hashes; bulky full attempt logs remain in the ignored run directory with digests in the report.

## Reproduce

With the existing native parity fixtures and local starter photos available:

```sh
python3 ios-benchmark/tools/prepare_adaptive_fixtures.py
PROOFCAM_ADAPTIVE_FIXTURES="$PWD/benchmark/runs/adaptive-fixtures-v3" swift test --package-path ios-benchmark/Core -c release --filter AdaptiveTests
PROOFCAM_TILED_FIXTURES="$PWD/benchmark/runs/adaptive-fixtures-v3" swift test --package-path ios-benchmark/Core -c release --filter TiledTests
python3 ios-benchmark/tools/simulate_adaptive.py /path/to/swift
python3 ios-benchmark/tools/compare_adaptive.py
```

The optional known-geometry probe is a development diagnostic, not blind recovery evidence. The simulation uses blind extraction.

## Remaining limits

Finite angle/scale searches do not guarantee arbitrary transformations or combinations. Crops removing every recoverable tile, severe downsampling/compression, perspective distortion, nonuniform scaling and difficult viewer backgrounds can still destroy recovery. Only five source images were evaluated. Apple SDK compilation, Apple codec tests, physical screenshots, visual inspection and iPhone performance remain pending. Run `bash ios-benchmark/tools/validate-mac.sh` on the Mac before device testing.
