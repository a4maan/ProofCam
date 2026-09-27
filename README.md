# ProofCam

ProofCam is an Android-first camera project that lets recipients check whether a photo matches a registered export and see which capture checks passed.

This folder is the project working directory. Product documentation, application code, backend code, and project tooling will live here as development proceeds.

## Current milestone

Steps 1 and 2 are documented in the [product brief](docs/01-product-brief.md) and [pilot scope and free development](docs/02-pilot-scope-and-free-development.md). These are planning decisions; implementation and device validation remain pending.

The Android photo pilot targets Android 14+ on existing or freely borrowed hardware. Development uses free tools, local compute, and no paid services. Pilot APKs will be distributed directly; hardware support is limited to configurations actually validated.

Step 3 is defined in the [threat model, privacy rules, and assurance policy](docs/03-threat-model-and-privacy-policy.md). Security controls are specified but not yet implemented or audited.

Step 4 is documented in the [capture and verification screen design](docs/04-capture-and-verification-design.md), with a [clickable local prototype](design/prototype.html) and [opening instructions](design/README.md). All prototype behavior is simulated.

Step 5 now has a working [benchmark harness](benchmark/README.md), **11,200 distinct source images**, 53 native-2048+ resolution variants, and a 300,000-case negative stress recipe plan. The [readiness record](docs/05-benchmark-data-and-harness.md) remains **in progress**: local corpus approval, actual screenshots, and final evaluation eligibility remain pending. Stress variants are not independent new photographs.

Step 6: the [desktop study is complete](docs/06-conventional-watermark-final-report.md), and an [Android research APK project](android-benchmark/README.md) is ready for device testing. Full step completion is **blocked: no Android phone is available**. Current candidates fail the required crop/rotation envelope and are not selected for production.

## Planning references

- [Original engineering specification](ProofCam_Product_Spec.docx)
- [Development roadmap](ProofCam_Android_Development_Roadmap.xlsx)

The original specification describes a broader release than the initial Android photo pilot. The product brief records the staged scope and the sharing-policy adjustment agreed during planning.

An [iPhone research port](ios-benchmark/README.md) is prepared for the available iPhone 16 Pro. Portable Swift core tests and raw-pixel cross-decoder checks pass; Xcode compilation and physical iPhone validation remain pending. This adds an iOS experiment without changing the Android-first product scope or clearing the Android hardware blocker.

The iPhone experiment defaults to an [adaptive tiled v3 watermark](ios-benchmark/ADAPTIVE-V3.md), with v1/v2 retained for comparison. It recovers all 125 marked host simulation cases, including the six previous v2 misses. The broader search is slower; device validation and product quality gates remain pending.

A [local provenance infrastructure prototype](provenance/README.md) now adds admitted device keys, signed requests, atomic registration, development certificates and independent exact-file verification. The iPhone app includes a camera-only capture path with Secure Enclave signing and durable request export, pending Apple/device validation. Capture origin and absence of AI remain **unverified**; platform attestation and production signing are not implemented.
