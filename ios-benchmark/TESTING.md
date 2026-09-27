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
