# Tiled recovery candidate v2

`ios-tiled-sign24-secded-v2` is an experimental alternative to the preserved `ios-qim12-bilinear-v1` candidate. The iPhone research app defaults to v2 for new runs; turn off **Use stronger tiled watermark (v2)** to repeat the old experiment. Screenshot decoding follows the candidate recorded in the current run, regardless of the switch's subsequent position. This does not port v2 to the Android app.

## Design

- Each complete **160×144-pixel tile** contains the full PC marker, 128-bit ID and CRC32. Payload tiles are independent, so cutting off the image edges need not destroy the remaining tiles' IDs.
- A fixed 64-bit synchronization marker identifies candidate tile positions. The decoder scans all integer pixel offsets, rather than assuming the screenshot begins on the original 8-pixel block grid.
- Each payload byte uses an extended Hamming (13,8) code: one erroneous bit can be corrected; two are rejected. The decoded frame must also pass PC marker and CRC32 validation. Neither code is a cryptographic authenticity check.
- The sign of DCT coefficient (1,2) carries each bit, at magnitude 24. This tolerates amplitude changes differently from the old QIM parity encoding, at the cost of greater image distortion.
- All four quarter turns and their mirrored versions are searched. Native, 512-, 768- and 1024-pixel long edges, plus half/double native size, are tried after deduplication. Views above a 1600-pixel long edge are excluded from this bounded search.
- Whole-image, uniform-border and density-based background crops are searched. The latter can ignore small controls on a mostly solid viewer background. It is a heuristic, not a general photo-region detector.
- Additional same-canvas deskew hypotheses cover −15° through +15° in one-degree steps (excluding zero) on the whole image capped at 1024 pixels. These are not a continuous angle estimator and are not combined with every mirror, crop or scale hypothesis.

The app normalizes v2 embedding to a 1024-pixel long edge, including upscaling small source images. The old v1 normalization remains unchanged. Very narrow images unable to hold a tile are rejected. Core simulations also exercise native 512-pixel sources to test lower-resolution behavior.

There are at most three regions, six distinct scale hypotheses per region, eight orientations and 30 additional deskew views: **174 view hypotheses**. All run even after detection, retaining conflicting IDs. Each view reports the first tile location for each distinct valid ID while still scanning for other IDs. Tile coordinates refer to the transformed view; region coordinates refer to the input image. Do not interpret either as an authenticity certificate.

## Evidence and reproduction

See [simulation outcomes](../benchmark/reports/step06-ios-tiled-simulation.json), [comparison with v1](../benchmark/reports/step06-ios-tiled-comparison.json), and [raw-pixel distortion](../benchmark/reports/step06-ios-tiled-quality.json). Misses are retained. These are development examples used while choosing the design, **not held-out qualification**. There are only three marked sources: two procedural images and one photo. A hundred additional procedural negatives do not establish a production false-positive rate.

After generating the existing native parity fixtures:

```sh
PROOFCAM_TILED_FIXTURES="$PWD/benchmark/runs/native-parity-v1" swift test --package-path ios-benchmark/Core -c release --filter TiledTests
PROOFCAM_TILED=1 python3 ios-benchmark/tools/simulate.py /path/to/swift
python3 ios-benchmark/tools/compare_tiled.py
```

The tiled tests exhaust all 256 byte values, every single-bit error position, and every two-bit error pair for the error-correction code. They also check crop recovery, conflicting IDs, pixel geometry, background cropping, and the fast coefficient filter against the original DCT implementation. An Apple JPEG test is provided for v2, but can only run on Apple platforms.

## Remaining limits

A crop that removes every complete recoverable tile can still fail. Very small/downsampled images, arbitrary angles, perspective warps, nonuniform scaling and combinations outside the tested search space are not solved. Large or complex viewer chrome may defeat automatic region localization. Repeated processing can destroy the signal even when each operation works separately.

This candidate changes pixels more strongly and searches more slowly than v1. Raw-pixel quality scores are not Apple JPEG quality measurements. Do not infer that the product's visual-quality or phone-latency targets have been met. Xcode compilation, actual Apple image conversion, device performance, visual inspection and physical screenshot tests remain required.
