# Step 6: Desktop conclusion and device blocker

Date: September 26, 2026. **Local deliverables complete; step 6 remains blocked on physical-device validation.** The user confirmed that no Android phone is available. No physical phone results, genuine screenshots, or mobile memory/latency qualification have been inferred from desktop work.

## Decision

**Do not select any current candidate for the production pilot.** The gentler registered QIM candidate has promising numerical image quality and limited synthetic border/scale recovery, but it fails the required crop/rotation envelope. The native-2048 probe also fails when reduced to the tested screenshot sizes. These are measured negative feasibility results, not unfinished attempts to make the report favorable. They do not prove that all conventional watermarking is infeasible.

The desktop study is concluded at this configuration. A future experiment would require a new pinned candidate/search configuration, such as crop/rotation synchronization or another algorithm family; it must not overwrite this evidence. Goal 7 has not been performed, and no support-envelope change is approved here.

## Delivered evidence

| Work | Outcome |
| --- | --- |
| Conventional comparison | Four Python configurations measured across the v1/v2 studies; preserved code, test IDs, source hashes, parameters, and complete predictions |
| Expanded tuning characterization | All 92 visually screened primary-photo candidates, 29 transforms each, plus 1,000 negative candidates: 3,668 scheduled cases |
| High-resolution probe | Nine original-resolution variants, five conditions each: 45 additional cases; same source families, not nine independent new subjects |
| Payload/coding | Full 128-bit public test ID + 16-bit experimental marker + 32-bit CRC; 176-bit repeated frame; majority voting is the only correction; no production issuer-routing field |
| Image quality | Mean RGB SSIM 0.99022, fifth percentile 0.98294 over the 91 successfully prepared pairs; one missing pair is explicitly excluded from quality and retained as failure in recovery |
| Native Android implementation | Installable offline research APK built; signature verified; no requested permissions; Android lint has zero errors and four warnings |
| Cross-language core checks | Full-ID extraction in both directions on three raw-RGB fixtures; midpoint-rounding differences recorded; no claim of byte-identical images or Android runtime validation |
| Dependency/license inventory | Pinned Python dependency versions and bundled-license hashes retained; Android tooling versions pinned; outbound repository licensing and redistribution review remain pending |
| Physical screenshots / mobile timing / peak memory | **Not measured: no phone available** |

The [expanded summary](../benchmark/reports/step06-desktop-final/summary.json) and adjacent cases/predictions/quality/score files preserve the evidence. Tests pass: 40 Python unit tests, plus host-JVM core round trips and input guards. Build and parity details are in [Android build evidence](../benchmark/reports/step06-android-build.json) and [native core checks](../benchmark/reports/step06-native-parity.json).

## Recovery and exclusions

| Condition | Complete expected IDs / scheduled sources |
| --- | --- |
| Original export | 91/92 |
| JPEG Q70 | 90/92 |
| 1024-pixel synthetic screenshot | 91/92 |
| 512-pixel resize / synthetic screenshot (each) | 83/92 |
| Each tested crop condition | 0/92 |
| Each tested rotation condition | 0/92 |
| Combined synthetic chain | 0/92 |

One positive source and six negative sources have unsupported ICC transformations. They were **not silently dropped or converted by discarding their profiles**. The positive source contributes a failure to all 29 scheduled conditions; the six negative failures remain incomplete searches. There were zero detections among **994 completed negative searches out of 1,000 scheduled**, not a successful 1,000-input false-positive gate. The scored buckets retain conditional bounds where applicable; no release false-positive bound or cryptographic acceptance result is claimed.

The [high-resolution probe](../benchmark/reports/step06-native-resolution/score.json) preserves its separate cohort: original and JPEG-Q70 recovery were 9/9, but resize-to-1024 and both synthetic screenshot sizes were 0/9. The extractor's fixed 1024 recovery target does not restore the 2048 embedding geometry after downscaling. Do not combine variant and parent observations into independent confidence samples.

Corpus rights/final eligibility remain pending from step 5. These are tuning measurements, not held-out release evaluation. Desktop timing was diagnostic with concurrent local build work; it is not a controlled speed comparison or Android cost evidence. The numerical quality results are not blinded display/artifact approval.

## Android test package

The [research app](../android-benchmark/README.md) is ready to install later on Android 14+. It implements photo selection, local benchmark iterations, marked-JPEG export, automatic or manually selected screenshot-region extraction, and JSON evidence export. It has no camera, network, certificate, or registration functionality.

Its candidate is deliberately named `android-qim12-bilinear-v1`: Android's image codecs/resampler and Java floating-point behavior differ from the desktop pipeline. Device qualification cannot inherit the Python scores. The APK records its own hash alongside device/build metadata, input/export/screenshot hashes, expected ID, attempts, and outcomes. Screenshots remain operator-attested. Hashing always covers the complete selected screenshot, including when a region is supplied for recovery.

The app's heap/PSS values are post-iteration samples, not incremental peak memory. Proper device profiling is still required. The UI and Android-specific code have not been executed on a device or emulator. APK construction and signature verification are not functional device tests.

## What unblocks completion

Access to an existing or freely borrowed Android 14+ phone is needed to execute the prepared protocol: verify app behavior, collect actual OS screenshots with viewer/version/scale and media-rectangle metadata, retain original files, measure native latency, profile peak memory, and review artifacts on the display. Record exact model/SKU, OS build/security patch, and APK hash; report unsupported and failed conditions.

Until that evidence exists, the original step 6 completion criterion is unmet. The roadmap says **Blocked — device unavailable**, while the desktop deliverables are complete. No purchase, paid service, fabricated evidence, or automatic narrowing of the product requirements is introduced.

## Reproduce the local study

```sh
python3 -m unittest discover -s benchmark/tests -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -m benchmark.conventional_final \
  --out benchmark/runs/conventional-final-new-version
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -m benchmark.native_resolution_probe \
  --out benchmark/runs/native-resolution-new-version \
  --parent-plan benchmark/runs/conventional-final-new-version/plan.json
```

Both commands require the locked source media locally and refuse an existing output directory. The first 24 test IDs are reused from v1; additional IDs are random and pinned in the new plan before measurement. Replay of an exact prior run uses its saved IDs. Preserve all unsupported cases. Native variants are exploratory and remain individually unreviewed.
