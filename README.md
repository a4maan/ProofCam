# ProofCam

ProofCam is an Android-first camera project that lets recipients check whether a photo matches a registered export and see which capture checks passed.

This folder is the project working directory. Product documentation, application code, backend code, and project tooling will live here as development proceeds.

## Current milestone

Steps 1 and 2 are documented in the [product brief](docs/01-product-brief.md) and [pilot scope and free development](docs/02-pilot-scope-and-free-development.md). These are planning decisions; implementation and device validation remain pending.

The Android photo pilot targets Android 14+ on existing or freely borrowed hardware. Development uses free tools, local compute, and no paid services. Pilot APKs will be distributed directly; hardware support is limited to configurations actually validated.

Step 3 is defined in the [threat model, privacy rules, and assurance policy](docs/03-threat-model-and-privacy-policy.md). Security controls are specified but not yet implemented or audited.

Step 4 is documented in the [capture and verification screen design](docs/04-capture-and-verification-design.md), with a [clickable local prototype](design/prototype.html) and [opening instructions](design/README.md). All prototype behavior is simulated.

Step 5 now has a working [benchmark harness](benchmark/README.md), **11,200 distinct source images**, 53 native-2048+ resolution variants, and a 300,000-case negative stress recipe plan. The [readiness record](docs/05-benchmark-data-and-harness.md) remains **in progress**: local corpus approval, actual screenshots, and final evaluation eligibility remain pending. Stress variants are not independent new photographs.

Next available work: step 6, benchmark conventional watermarks on the tuning split while completing corpus readiness.

## Planning references

- [Original engineering specification](ProofCam_Product_Spec.docx)
- [Development roadmap](ProofCam_Android_Development_Roadmap.xlsx)

The original specification describes a broader release than the initial Android photo pilot. The product brief records the staged scope and the sharing-policy adjustment agreed during planning.

Step 6 is **in progress**: [conventional watermark experiments](docs/06-conventional-watermark-benchmarks.md) now implement two full-ID DCT baselines and a tuning-only comparison. Physical-device measurements and actual screenshot recovery remain pending.

Step 6 continuation adds [bounded scale and border recovery](benchmark/REGISTERED.md), tested on the same tuning photos and full IDs. Results remain desktop research, with crop/rotation and physical-device qualification outstanding.
