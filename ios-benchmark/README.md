# ProofCam iPhone research app

An iOS 17+ SwiftUI port of the Android watermark experiment, intended for the available **iPhone 16 Pro**. This is research software, not the production capture/certificate app. It uses free local tools without analytics or automatic media uploads. Default builds make no app network requests; optional App Attest calls contact Apple. A separate [local provenance service](../provenance/README.md) now accepts device-signed requests exported from the camera experiment; it issues development records only.

**Status:** source and Xcode project prepared. Portable Swift tests, synthetic geometry simulations, and three raw RGB cross-decoder fixtures passed on Linux with Swift 6.0.3. The app source passes Swift syntax parsing. See the [test audit](TESTING.md) for coverage and outstanding checks. **No Apple SDK typecheck, Xcode build, simulator run, signing, or physical iPhone test has been performed here.** Run the Mac validation below before collecting evidence. See [host parity results](../benchmark/reports/step06-ios-parity.json).

## Open on your Mac

1. Clone `https://github.com/a4maan/ProofCam.git`, or run `git pull` in your existing checkout.
2. From the repository root, run `bash ios-benchmark/tools/validate-mac.sh`. This runs Debug and Release core tests, six Apple image-codec tests and two CryptoKit provenance tests on macOS, and an unsigned Release simulator build. A successful simulator build is not device validation.
3. Open `ios-benchmark/ProofCamResearch.xcodeproj`. In the ProofCamResearch target's **Signing & Capabilities**, select your Personal Team. If needed, change the bundle identifier to one unique to your account.
4. Connect and trust your iPhone 16 Pro, enable Developer Mode if Xcode requests it, select the physical phone as the run destination, and press Run. The shared scheme uses Release optimization for useful timings. Stop the debugger and launch the installed app directly before collecting measurements.

Xcode and a free Apple Account support personal device testing; free provisioning needs periodic renewal. No paid Developer Program membership or TestFlight is required for this workflow. [Apple membership comparison](https://developer.apple.com/support/compare-memberships/).

## Capture provenance experiment

The new **Capture provenance — development** section captures directly from the camera and binds the finalized watermarked JPEG to a Secure Enclave signature. It saves pending JPEG/request pairs across app launches. Enrollment, submission to the local development service, and independent verification follow the [provenance instructions](../provenance/README.md). There is no automatic mobile upload, server-attested camera-origin claim, or proof of absence of AI. The optional [App Attest integration](../provenance/APP-ATTEST.md) adds server checks on app-bound request evidence, requires eligible Apple provisioning, and stays inactive in the default free build. This path has only been syntax-checked here; run the Mac/iPhone checks before relying on it.

## Run a watermark experiment

1. Save an opaque JPEG/PNG test image to Files. HEIC and transparent PNG inputs are unsupported. Import via **Choose image and run 20 samples**. Files gives the app the selected file bytes, which are hashed without rewriting. Keep that source file.
2. Wait for three warmups and 20 measured iterations. Each iteration embeds a fresh run's common 128-bit random ID, encodes Apple JPEG at quality 0.95, decodes that JPEG, and runs bounded recovery. Image normalization and JPEG decode time are excluded from the reported embed/extract timings; JPEG encoding is included in embed time. Timings are milliseconds; displayed p95 is nearest rank, sample 19 of 20 sorted values. JSON contains every sample.
3. Save the marked JPEG. Open it in your normal photo viewer, take an actual iOS screenshot, and save that screenshot to Files. Retain the untouched screenshot.
4. Import the screenshot. Mark the OS capture declaration only when true. It is operator testimony, not hardware attestation. Optionally specify `left,top,right,bottom` in orientation-normalized screenshot pixels. Recovery records that manual region separately and still hashes the entire provided screenshot file. Attempt rectangles are relative to the selected region. Run without a manual rectangle first to preserve automatic results, then repeat with a rectangle if useful.
5. Export the research JSON and retain it with the source, marked JPEG, and screenshot. Record viewer name/version and display/zoom scale separately. Record Xcode version and git revision. The JSON records the exact operating system, hardware model, runtime kind, input dimensions after scaling, executable SHA-256 when readable, source/JPEG/screenshot hashes, expected ID, all recovery attempts and all timing samples. The executable hash is not a whole-app/IPA hash.

A new source clears the previous run, including when loading fails. Results are in memory until exported; export before starting another source or closing the app. Selecting a cloud-backed Files location may involve the OS file provider; the app itself has no upload service.

## Candidate and limits

New runs default to [adaptive tiled candidate v3](ADAPTIVE-V3.md), which recovered all 125 marked cases in the current host simulation. Select v1 or v2 for comparison. V3 improves geometric recovery and photo SSIM over v2, but its broader search is slower. V2 and v3 normalize embedding to a 1024-pixel long edge with upscaling. The description below documents the preserved v1 baseline.


`ios-qim12-bilinear-v1` uses the same 176-bit PC + full 128-bit ID + CRC32 framing, three-frame minimum capacity, coefficient (1,2) QIM with step 12, and bounded native/1024/uniform-border search. Every eligible search view runs even after a detection, retaining conflicting IDs. A CRC checks accidental errors; it is not a signature or authenticity proof.

Inputs are capped at 25 MiB, 20 megapixels and 16384 pixels per side. ImageIO normalizes orientation and CoreGraphics renders opaque 8-bit sRGB. Embedding scales to a maximum long edge of 1024 without upscaling. The portable resampler explicitly uses pixel-center bilinear interpolation. Apple image decoding/color conversion/JPEG differ from Android and Python, so neither desktop nor Android results qualify this candidate. Cross-decoder checks allow verified floating-point midpoint differences of up to six channel levels; pixels are not byte-identical.

The principal workflow matches Android, but this first port uses Files import and **does not measure memory** (`not_measured` in JSON). It does not yet establish identical platform performance or robustness. Crop/rotation weaknesses in the conventional algorithm remain. Twenty repeated timings are not twenty independent robustness samples. Physical iPhone evidence does not clear the Android-device blocker for roadmap step 6.

## Reproduce host checks

With Swift 5.9+:

```sh
swift test --package-path ios-benchmark/Core -c release
```

For cross-decoder checks, first create the ignored fixtures using the Android [host parity procedure](../android-benchmark/README.md), then:

```sh
swift build --package-path ios-benchmark/Core -c release
python3 ios-benchmark/tools/check_parity.py ios-benchmark/Core/.build/release/CoreParity
```

The Python checker uses the existing benchmark Python dependencies and records source hashes. It checks Python/Java-to-Swift extraction, Swift round trips, Swift-to-Python extraction, and pixel differences against known QIM midpoint locations. It does not run any Apple code. `tools/create_project.py` regenerates the checked-in Xcode project deterministically; no third-party Xcode project generator is needed.
