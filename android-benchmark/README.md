# ProofCam Android research benchmark

This is an offline, installable test app for the device-dependent portion of roadmap step 6. It is **not** the production camera app, a certificate issuer, or a claim that the conventional watermark meets the pilot requirements. There is no network or camera permission and no account/service dependency.

The app uses Java and Android framework APIs to keep this isolated experiment small. Kotlin/Compose remains the working choice for the future product app. The native candidate is named `android-qim12-bilinear-v1`: Android image decoding, JPEG encoding and bilinear resampling differ from the Python/Pillow/Lanczos research pipeline. Do not transfer desktop recovery/quality measurements to this candidate.

## Build and host checks

Requirements: JDK 17 or later, Android SDK platform 35 and build-tools 35.0.0, and the checked-in Gradle 8.13 wrapper. Android Gradle Plugin is pinned to 8.13.0. This is a deliberately pinned direct-install research build, not a current Google Play target-policy claim. The app requires Android 14/API 34 or newer.

Set `ANDROID_HOME` to your SDK, or put `sdk.dir=/absolute/path/to/sdk` in ignored `local.properties`. From this directory:

```sh
./gradlew :app:assembleDebug :app:lintDebug
```

The APK is `app/build/outputs/apk/debug/app-debug.apk`. Its development signing key stays outside the repository; it is not a production signing credential. Gradle's distribution checksum is pinned. Official tooling references: [SDK manager](https://developer.android.com/tools/sdkmanager), [AGP 8.13 compatibility](https://developer.android.com/build/releases/agp-8-13-0-release-notes).

From the repository root, with `java` and `javac` on PATH and the benchmark Python dependencies installed:

```sh
python3 android-benchmark/tools/check_parity.py
```

The host test checks both extraction directions using a photo and two procedural RGB fixtures, native round trips, a flat negative, invalid ID rejection, and capacity limits. It does **not** run Android. Java double precision and Python float32 can choose opposite valid quantization points at exact midpoints; observed differences greater than one channel level are checked against those midpoint locations. The images are not byte-equivalent. Android JPEG, resampling, UI behavior, and physical cost still require device tests.

## Collect real device evidence when a phone is available

1. Install the APK directly, or use `adb -d install -r app/build/outputs/apk/debug/app-debug.apk` for a connected physical phone. No paid store enrollment is needed.
2. Choose an opaque JPEG/PNG test photo. The app caps encoded inputs at 25 MiB, decoded inputs at 20 megapixels/16384 pixels per side, and benchmark embedding at a 1024-pixel long edge without upscaling.
3. Run the benchmark. It creates a random public 128-bit test ID, executes three warmups and 20 measured iterations, and records individual recovery results plus nearest-rank p95 timings. Repeated timings on one photo are not 20 independent robustness samples.
4. Save the marked JPEG and display it in the phone's normal gallery/viewer. Capture an actual OS screenshot. Retain the untouched screenshot file.
5. Select that screenshot in the app. Check the OS-screenshot declaration only if it was actually captured on this phone. The declaration is operator-attested, not hardware proof. Automatic extraction searches the full image and simple uniform-border regions at native/1024 scale. Optionally enter the actual media rectangle in original screenshot pixels (`left,top,right,bottom`); manual and automatic results must be reported separately. Rectangle selection never changes the recorded hash of the full screenshot bytes.
6. Save the JSON evidence after decoding. Keep the selected original source, final marked JPEG, untouched screenshot, and JSON together. Also record the viewing app name/version and zoom/display scale; the benchmark app cannot infer those facts. Each new photo/run replaces in-memory results; export before starting another sample. Nothing is uploaded automatically.

The JSON records device model, OS/build/security patch, ABI, APK hash, input/export/screenshot hashes, expected ID, attempt geometry, recovered IDs, individual timings, and manual/automatic region selection. All declared extraction views run even after success, and conflicting IDs remain failures. Image decode and normalization are outside the extraction timing; embedding timing includes JPEG encoding but excludes source normalization. No end-to-end capture latency is claimed.

Memory figures are post-iteration heap/PSS samples including warmups, **not incremental peak memory**. Use a device profiler before evaluating the memory gate. UI/instrumentation testing has not occurred without a device. The app does not replace the screenshot importer's frozen-corpus eligibility checks or silently add evidence to the release dataset.

The current candidate cannot recover general crops/rotation. Record failures. Do not label a recovered ID as image authenticity or integrity: there is no signing/registration/verification service in this app.

## Current availability

The user confirmed on September 26, 2026 that no Android phone is available. ADB also listed no device in this environment. The APK is prepared for later testing. No emulator, fixture, host-JVM run, or synthetic canvas counts as physical Android evidence; step 6's device-dependent criteria remain blocked.
