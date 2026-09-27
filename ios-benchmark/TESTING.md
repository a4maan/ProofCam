# iPhone port test audit — 2026-09-26

This is a host validation record, not a claim that the app works in every situation. The available machine is Linux/WSL, with Swift 6.0.3 and no Xcode or connected iPhone. Apple build and device gates remain open.

## Executed checks

| Check | Result | What it covers |
| --- | --- | --- |
| Portable Swift tests, Release | 19 passed | CRC known vector and payload corruption; valid/invalid IDs; RGB dimensions/alpha; exact minimum capacity; incomplete blocks; deterministic noise round trips; unmarked negatives; crops; resizing; border recovery; bounded search and conflicting IDs; JSON round trip; rectangle parsing; p95; short/oversized/error file reads |
| Portable Swift tests, Debug | 19 passed | Same assertions with Debug compilation |
| Existing Python suite | 40 passed | Existing benchmark/harness regression tests |
| Cross-decoder fixtures | 3 passed | Python/Java to Swift, Swift to Python, Swift round trips; channel differences constrained to verified QIM midpoint locations |
| App and Apple codec Swift parsing | Passed | Syntax only, not SDK type checking |
| Xcode project consistency | Passed | Reproducible generator output, valid scheme XML, inclusion of all app/core Swift sources |
| Mac script syntax | Passed | Shell syntax only |
| Parity CLI missing argument | Passed | Clear usage error and exit status 2, rather than argument-index crash |

The deterministic-noise test uses 20 images, each tested both unmarked and marked. These small fixtures exercise correctness; they are not a statistical robustness or image-quality qualification. Existing crop/rotation weaknesses are unchanged.

## Fixes from this review

- Read imported files until EOF, accommodating short reads and rejecting files over the limit instead of silently accepting a prefix.
- Replace a fixed percentile array index with a tested nearest-rank calculation that handles empty/invalid samples.
- Prevent external clients from mutating validated image pixels into invalid storage.
- Reset manual rectangle and screenshot declaration when selecting a new benchmark source.
- Drain Apple autoreleased objects each measured iteration to limit temporary-object accumulation. Device memory consumption remains unmeasured.
- Handle missing CLI arguments and malformed fixture rows explicitly.
- Extract Apple image conversion into a testable module shared by the app and Mac test suite.

## Prepared but NOT executed

Four Apple codec tests compile conditionally on Apple platforms: exact PNG pixel order, malformed/oversized/transparent inputs, Apple JPEG watermark recovery, and orientation normalization. Linux excludes them; they are not included in the 19 passing tests. `bash ios-benchmark/tools/validate-mac.sh` runs them in Debug and Release before attempting an unsigned simulator build. Failures stop validation.

Still required on macOS/iPhone:

- Xcode compile/link and launch; signing/install on the iPhone 16 Pro.
- File-provider import/export and cancellation, new-run failure state, app backgrounding/relaunch, and saved JSON/JPEG contents.
- UI layout, accessibility/Dynamic Type and VoiceOver, keyboard interaction, real screenshot selection and manual coordinates.
- Real JPEG/PNG orientation and color-profile variety, large inputs, sustained memory use and thermal/performance behavior.
- Actual screenshot recovery in chosen viewers/zoom settings. Capture failures as results, not exclusions.

There are no automated UI tests yet. The host checks cannot establish that the Apple APIs, permissions, file providers, or physical device behave correctly. No paid cloud build, remote Mac, or external device service was used.

## Additional host simulations and sanitizer pass

The additional suite includes 2,000 deterministic malformed/valid crop rectangles, four extreme aspect ratios, and **145 synthetic cases** decoded by the actual Swift bounded-search candidate. Results are retained in [the simulation report](../benchmark/reports/step06-ios-simulation.json), including misses and every search attempt.

| Synthetic condition | Full-ID matches |
| --- | --- |
| native | 3/3 |
| pillow_jpeg_95 | 3/3 |
| pillow_jpeg_85 | 3/3 |
| pillow_jpeg_70 | 3/3 |
| resize_512 | 2/3 |
| uniform_screenshot_512 | 2/3 |
| resize_768 | 1/3 |
| uniform_screenshot_768 | 1/3 |
| resize_1024 | 1/3 |
| uniform_screenshot_1024 | 1/3 |
| crop_10percent | 0/3 |
| rotate_90 | 0/3 |
| mirror | 0/3 |
| nonuniform_chrome | 0/3 |
| manual_rectangle | 3/3 |

The 100 unmarked procedural noise images produced zero detections. JPEG tests use Pillow, not Apple's codec. There are only three marked sources (two procedural images, one photo); these are small functional probes, not estimates of production reliability. The manual-rectangle case supplies the exact known media bounds; it does not show automatic localization or robustness to imprecise selection.

**Findings:** compression worked on these examples, but rescaling was inconsistent. Cropping, rotation, mirroring, and nonuniform viewer chrome defeated automatic recovery in all tested examples. Exact manual extraction recovered all three examples with viewer chrome. A passing test run means outcomes were recorded without crashes or unexpected IDs; it does not mean every transformation recovered successfully.

A Debug AddressSanitizer run passed 21 tests with no reported address-safety errors. One additional fixture-dependent simulation test was explicitly skipped in that sanitizer run; the 145-case matrix ran separately in Release. Leak detection was disabled (`ASAN_OPTIONS=detect_leaks=0`), so this is not a leak test or an iOS memory qualification. Apple-only tests remain excluded on Linux.

Reproduce after the raw cross-decoder fixtures have been generated:

```sh
python3 ios-benchmark/tools/simulate.py /path/to/swift
ASAN_OPTIONS=detect_leaks=0 swift test --package-path ios-benchmark/Core --scratch-path /tmp/proofcam-swift-asan --sanitize=address -c debug
```

The simulator stores generated pixels under ignored `benchmark/runs/ios-simulation-v1/`; the manifest hashes each input. No phone, Apple image codec, Apple SDK, or GUI was simulated.
